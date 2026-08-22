"""Odoo shell input: safely process the pending customer migration in commits."""

BATCH_ID = 13
RECORDS_PER_COMMIT = 25

batch_model = env['utility.migration.batch']
customer_model = env['utility.migration.customer']

while True:
    batch = batch_model.browse(BATCH_ID).exists()
    if not batch:
        raise RuntimeError('Migration batch 13 was not found.')

    pending_count = customer_model.search_count([
        ('last_batch_id', '=', batch.id),
        ('state', 'in', ('queued', 'processing')),
    ])
    if not pending_count:
        print('Migration is complete.')
        break

    batch.action_process_batch(max_records_per_run=RECORDS_PER_COMMIT)
    env.cr.commit()
    batch.invalidate_recordset()
    print(
        'processed=%s success=%s errors=%s remaining=%s' % (
            batch.processed_count,
            batch.success_count,
            batch.error_count,
            max(pending_count - RECORDS_PER_COMMIT, 0),
        ),
        flush=True,
    )
