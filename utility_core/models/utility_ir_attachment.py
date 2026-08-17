import os
import logging
import re
from odoo import models, api, fields
from odoo.tools import config
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    invoice_attachment_url = fields.Char(
        string='رابط المرفق',
        compute='_compute_invoice_attachment_url',
        store=True,
    )
    custom_storage_path = fields.Char(
        string='مسار التخزين المخصص',
        readonly=True,
    )

    _image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')

    @api.depends('res_model', 'res_id', 'name', 'store_fname')
    def _compute_invoice_attachment_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for attachment in self:
            attachment.invoice_attachment_url = False
            if attachment.res_model in ('account.move', 'account.invoice') and attachment.res_id:
                fname = attachment.name
                if fname:
                    attachment.invoice_attachment_url = '%s/web/image/ir.attachment/%s/%s' % (
                        base_url, attachment.id, fname)

    @api.model
    def _is_image_context(self, vals=None):
        vals = vals or {}
        mimetype = vals.get('mimetype') or self._context.get('mimetype', '')
        fname = (vals.get('name', '')
                 or vals.get('datas_fname', '')
                 or self._context.get('name', '')
                 or self._context.get('filename', '')
                 or self._context.get('default_name', ''))
        if mimetype and mimetype.startswith('image/'):
            return True
        if fname and fname.lower().endswith(self._image_extensions):
            return True
        return False

    @api.model
    def _sanitize_storage_component(self, value, fallback='unknown'):
        value = re.sub(r'[^A-Za-z0-9_.-]+', '_', value or '')
        return value.strip('._-') or fallback

    @api.model
    def _get_storage_module(self, model_name):
        if model_name and model_name in self.env:
            return self._sanitize_storage_component(
                getattr(self.env[model_name], '_original_module', False)
                or getattr(self.env[model_name], '_module', False),
                fallback='base',
            )
        return self._sanitize_storage_component(
            (model_name or '').split('.', 1)[0],
            fallback='unlinked',
        )

    @api.model
    def _get_storage_bucket(self, model_name=None, storage_date=None):
        model_name = model_name or self._context.get('res_model') or self._context.get('default_res_model')
        model_component = self._sanitize_storage_component(
            model_name.replace('.', '_') if model_name else '',
            fallback='unlinked',
        )
        module_component = self._get_storage_module(model_name)
        storage_date = storage_date or fields.Datetime.now()
        date_component = storage_date.strftime('%Y/%m/%d')
        return os.path.join(module_component, model_component, date_component)

    @api.model
    def _get_custom_path(self, model_name=None, storage_date=None):
        return os.path.join(
            config['data_dir'], 'filestore', self.env.cr.dbname,
            self._get_storage_bucket(model_name=model_name, storage_date=storage_date),
        )

    @api.model
    def _get_storage_context(self, vals):
        model_name = vals.get('res_model') or self._context.get('res_model') or self._context.get('default_res_model')
        storage_date = fields.Datetime.now()
        bucket = self._get_storage_bucket(model_name=model_name, storage_date=storage_date)
        return {
            'utility_attachment_storage_bucket': bucket,
            'utility_attachment_storage_path': self._get_custom_path(
                model_name=model_name, storage_date=storage_date,
            ),
        }

    @api.model
    def _file_read(self, fname, bin_size=False):
        # New files use a complete relative path in store_fname and are handled
        # by Odoo's standard implementation, including old standard Filestore files.
        data = super()._file_read(fname, bin_size=bin_size)
        if data:
            return data

        # Compatibility for files written by the former custom override, where
        # store_fname contained only the hash and the directory was stored on the row.
        attachment = self.sudo().search([
            ('store_fname', '=', fname),
            ('custom_storage_path', '!=', False),
        ], limit=1)
        if attachment:
            try:
                with open(os.path.join(attachment.custom_storage_path, os.path.basename(fname)), 'rb') as stream:
                    return stream.read()
            except (IOError, OSError):
                _logger.info('Legacy attachment path is unavailable: %s', fname, exc_info=True)
        return b''

    @api.model
    def _file_write(self, bin_data, checksum):
        bucket = self._context.get('utility_attachment_storage_bucket')
        if not bucket:
            return super()._file_write(bin_data, checksum)

        fname = '%s/%s' % (bucket.replace(os.sep, '/'), checksum)
        full_path = self._full_path(fname)
        directory = os.path.dirname(full_path)
        try:
            os.makedirs(directory, exist_ok=True)
            if os.path.exists(full_path):
                if not self._same_content(bin_data, full_path):
                    raise UserError(_('تعارض في محتوى مرفق له نفس البصمة.'))
            else:
                with open(full_path, 'wb') as stream:
                    stream.write(bin_data)
            self._mark_for_gc(fname)
            return fname
        except (IOError, OSError) as exc:
            _logger.error('Structured attachment storage failed for %s: %s', fname, exc)
            raise UserError(_('تعذر حفظ المرفق في Filestore المنظم.')) from exc

    @api.model
    def _file_delete(self, fname):
        # Odoo's GC handles structured paths and standard paths through the
        # checklist. The direct legacy cleanup is needed only for old rows.
        if '/' not in fname.replace('\\', '/'):
            attachment = self.sudo().search([
                ('store_fname', '=', fname),
                ('custom_storage_path', '!=', False),
            ], limit=1)
            if attachment:
                try:
                    os.remove(os.path.join(attachment.custom_storage_path, os.path.basename(fname)))
                    return
                except FileNotFoundError:
                    return
                except OSError:
                    _logger.info('Could not delete legacy attachment file: %s', fname, exc_info=True)
        return super()._file_delete(fname)

    @api.model_create_multi
    def create(self, vals_list):
        # Base Odoo writes binary data before the attachment row exists. Split
        # mixed create calls so each group receives one deterministic bucket.
        groups = {}
        for index, vals in enumerate(vals_list):
            context = self._get_storage_context(vals)
            key = (context['utility_attachment_storage_bucket'], context['utility_attachment_storage_path'])
            groups.setdefault(key, []).append((index, vals, context))

        created_by_index = {}
        for entries in groups.values():
            context = entries[0][2]
            group_vals = [entry[1] for entry in entries]
            attachments = super(IrAttachment, self.with_context(**context)).create(group_vals)
            for entry, attachment in zip(entries, attachments):
                created_by_index[entry[0]] = attachment
                if attachment.store_fname:
                    attachment.write({'custom_storage_path': context['utility_attachment_storage_path']})

        return self.browse([created_by_index[index].id for index in range(len(vals_list))])
