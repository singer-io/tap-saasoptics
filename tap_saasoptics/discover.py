from singer.catalog import Catalog, CatalogEntry, Schema
from tap_saasoptics.schema import get_schemas, STREAMS

def discover():
    schemas, field_metadata = get_schemas()
    catalog = Catalog([])

    for stream_name, schema_dict in schemas.items():
        schema = Schema.from_dict(schema_dict)
        mdata = field_metadata[stream_name]

        if stream_name == 'deleted':
            # Only generate one schema for deleted, but they all have the same PKs
            key_properties = STREAMS['deleted_contracts']['key_properties']
        else:
            key_properties = STREAMS[stream_name]['key_properties']
        catalog.streams.append(CatalogEntry(
            stream=stream_name,
            tap_stream_id=stream_name,
            key_properties=key_properties,
            schema=schema,
            metadata=mdata
        ))

    return catalog
