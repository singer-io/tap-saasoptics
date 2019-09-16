# de-nest auditentry with auditentry__ prefix for: invoices, transactions
def denest_auditentry(this_json, path):
    new_json = this_json
    i = 0
    for record in list(this_json.get(path, [])):
        if 'auditentry' in record:
            for key, val in record['auditentry'].copy().items():
                new_json[path][i]['auditentry_{}'.format(key)] = val
            new_json[path][i].pop('auditentry')
        i = i + 1
    return new_json


# Run all transforms: convert string numbers to float and
#  de-nest auditentry node for invoices and transactions
def transform_json(this_json, stream, path):
    new_json = this_json
    if stream in ('invoices', 'transactions'):
        denested_json = denest_auditentry(new_json, path)
        new_json = denested_json
    if path in new_json:
        return new_json[path]
    else:
        return new_json