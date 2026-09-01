import singer
from singer.catalog import Catalog, CatalogEntry, Schema

from tap_saasoptics.client import SaaSOpticsForbiddenError, SaaSOpticsUnauthorizedError
from tap_saasoptics.schema import STREAMS, get_schemas

LOGGER = singer.get_logger()


def _check_stream_access(client, stream_name, stream_config):
    """Return True when stream is accessible, False on 403."""
    path = stream_config.get('path', stream_name)
    try:
        client.get(path, endpoint=f'discover:{stream_name}')
        return True
    except (SaaSOpticsForbiddenError, SaaSOpticsUnauthorizedError) as exc:
        LOGGER.warning(
            "Excluding unauthorized stream '%s' from catalog. API error: %s",
            stream_name,
            exc,
        )
        return False


def _apply_access_checks(client, schemas: dict, field_metadata: dict) -> None:
    """Exclude streams the credentials cannot read (403) from discovery output."""
    if client is None:
        return

    inaccessible_streams = [
        stream_name
        for stream_name, stream_cfg in STREAMS.items()
        if stream_name in schemas
        and not stream_cfg.get('parent')
        and not _check_stream_access(client, stream_name, stream_cfg)
    ]

    for stream_name in inaccessible_streams:
        schemas.pop(stream_name, None)
        field_metadata.pop(stream_name, None)

    if not schemas:
        raise SaaSOpticsForbiddenError(
            "HTTP-error-code: 403, Error: The credentials do not have 'read' access to any supported streams."
        )

    if inaccessible_streams:
        LOGGER.warning(
            "Unauthorized streams excluded from catalog: %s",
            ', '.join(inaccessible_streams),
        )


def discover(client=None):
    schemas, field_metadata = get_schemas()
    _apply_access_checks(client, schemas, field_metadata)
    catalog = Catalog([])

    for stream_name, schema_dict in schemas.items():
        schema = Schema.from_dict(schema_dict)
        mdata = field_metadata[stream_name]
        stream_metadata = STREAMS[stream_name]

        catalog.streams.append(CatalogEntry(
            stream=stream_name,
            tap_stream_id=stream_name,
            key_properties=stream_metadata['key_properties'],
            schema=schema,
            metadata=mdata
        ))

    return catalog
