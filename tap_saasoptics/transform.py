import re
from re import sub


# de-nest auditentry with auditentry__ prefix for: invoices, transactions
def denest_auditentry(this_json, path):
    new_json = this_json
    i = 0
    for record in list(this_json[path]):
        if 'auditentry' in record:
            for key, val in record['auditentry'].copy().items():
                new_json[path][i]['auditentry_{}'.format(key)] = val
            new_json[path][i].pop('auditentry')
        i = i + 1
    return new_json

# Function for converting string number to float
def string_to_float(val):
    try:
        new_val = float(val)
        return new_val
    except ValueError:
        
        return None

    
# Loop through arrays for converting string number to float
def convert_string_to_float_array(arr):
    new_arr = []
    for i in arr:
        if isinstance(i, list):
            new_arr.append(convert_string_to_float_array(i))
        elif isinstance(i, dict):
            new_arr.append(convert_string_to_float_dict(i))
        else:
            new_arr.append(i)
    return new_arr


# Convert string numbers to float for a nested dict with lists
def convert_string_to_float_dict(this_dict):
    key_endings = ('_amount', '_rate', 'percentage', 'subtotal', 'probability',
                   'qantity', 'balance', 'number_field1', 'number_field2',
                   'number_field3')
                   # '_tax', 'factor'?
    new_dict = {}
    for key, val in this_dict.items():
        if isinstance(this_dict[key], str) and key.endswith(key_endings):
            new_dict[key] = string_to_float(val)
        elif isinstance(this_dict[key], dict):
            new_dict[key] = convert_string_to_float_dict(this_dict[key])
        elif isinstance(this_dict[key], list):
            new_dict[key] = convert_string_to_float_array(this_dict[key])
        else:
            new_dict[key] = this_dict[key]
    return new_dict


# Run all transforms: convert string numbers to float and
#  de-nest auditentry node for invoices and transactions
def transform_json(this_json, stream, path):
    new_json = convert_string_to_float_dict(this_json)
    if stream in ('invoices', 'transactions'):
        denested_json = denest_auditentry(new_json, path)
        new_json = denested_json
    return new_json[path]
