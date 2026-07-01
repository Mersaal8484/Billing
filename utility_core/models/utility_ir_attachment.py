import os
import logging
from datetime import datetime
from odoo import models, api, fields
from odoo.tools import config

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    invoice_attachment_url = fields.Char(
        string='Attachment URL',
        compute='_compute_invoice_attachment_url',
        store=True,
    )
    custom_storage_path = fields.Char(
        string='Custom Storage Path',
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
    def _get_custom_path(self, model_name=None):
        table = 'unknown'
        res_model = model_name or self._context.get('res_model') or self._context.get('default_res_model', '')
        if res_model:
            if res_model in self.env:
                table = self.env[res_model]._table
            else:
                table = res_model.replace('.', '_')
        return os.path.join(
            config['data_dir'], 'filestore',
            self.env.cr.dbname,
            table,
            datetime.now().strftime('%Y_%m'),
        )

    @api.model
    def _store_file_read(self, fname, bin_size=False):
        # 1. First, search for the attachment record to get the exact custom_storage_path
        attachment = self.sudo().search([('store_fname', '=', fname)], limit=1)
        if attachment and attachment.custom_storage_path:
            try:
                with open(os.path.join(attachment.custom_storage_path, fname), 'rb') as f:
                    return f.read()
            except IOError:
                pass
        
        # 2. Fallback to context-based custom path if not found
        if self._context.get('force_custom_storage') or self._is_image_context():
            path = self._get_custom_path()
            try:
                with open(os.path.join(path, fname), 'rb') as f:
                    return f.read()
            except IOError:
                pass
        
        # 3. Default Odoo filestore read
        return super()._store_file_read(fname, bin_size=bin_size)

    @api.model
    def _store_file_write(self, key, bin_data):
        if self._context.get('force_custom_storage') or self._is_image_context():
            path = self._get_custom_path()
            try:
                os.makedirs(path, exist_ok=True)
                with open(os.path.join(path, key), 'wb') as f:
                    f.write(bin_data)
                return key
            except IOError as e:
                _logger.error('Custom storage failed, using default: %s', e)
        return super()._store_file_write(key, bin_data)

    @api.model
    def _store_file_delete(self, fname):
        attachment = self.sudo().search([('store_fname', '=', fname)], limit=1)
        if attachment and attachment.custom_storage_path:
            try:
                os.remove(os.path.join(attachment.custom_storage_path, fname))
                return
            except IOError:
                pass

        if self._context.get('force_custom_storage') or self._is_image_context():
            path = self._get_custom_path()
            try:
                os.remove(os.path.join(path, fname))
                return
            except IOError:
                pass
        return super()._store_file_delete(fname)

    @api.model_create_multi
    def create(self, vals_list):
        attachments = super().create(vals_list)
        for attachment, vals in zip(attachments, vals_list):
            is_image = (
                (attachment.mimetype or '').startswith('image/')
                or (attachment.name or '').lower().endswith(self._image_extensions)
                or self._is_image_context(vals)
            )
            if is_image and attachment.store_fname:
                res_model = vals.get('res_model') or attachment.res_model
                attachment.write({'custom_storage_path': self._get_custom_path(model_name=res_model)})
        return attachments
