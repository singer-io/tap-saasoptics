import singer
from singer.catalog import Catalog, CatalogEntry, Schema

from tap_saasoptics.client import SaaSOpticsForbiddenError
from tap_saasoptics.schema import STREAMS, get_schemas

LOGGER = singer.get_logger()


def _check_stream_access(client, stream_name, stream_config):
    """Return True when stream is accessible, False on 403."""
    path = stream_config.get('path', stream_name)
    try:
        client.get(path, endpoint=f'discover:{stream_name}')
        return True
    except SaaSOpticsForbiddenError:
        LOGGER.warning(
            "No 'read' access to stream '%s'. Excluded from catalog.",
            stream_name,
        )
        return False


def _prune_inaccessible_children(schemas: dict, field_metadata: dict) -> list:
    """Remove child streams when their parent stream is inaccessible."""
    inaccessible_children = []
    for stream_name, stream_cfg in list(STREAMS.items()):
        parent = stream_cfg.get('parent')
        if stream_name in schemas and parent and parent not in schemas:
            LOGGER.warning(
                "Stream '%s' excluded from catalog because its parent stream '%s' is not accessible.",
                stream_name,
                parent,
            )
            schemas.pop(stream_name, None)
            field_metadata.pop(stream_name, None)
            inaccessible_children.append(stream_name)

    return inaccessible_children


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

    inaccessible_children = _prune_inaccessible_children(schemas, field_metadata)
    all_inaccessible = inaccessible_streams + [
        stream_name
        for stream_name in inaccessible_children
        if stream_name not in inaccessible_streams
    ]

    if not schemas:
        raise SaaSOpticsForbiddenError(
            "HTTP-error-code: 403, Error: The credentials do not have 'read' access to any supported streams."
        )

    if all_inaccessible:
        LOGGER.warning(
            "No 'read' access to stream(s): %s. Excluded from catalog.",
            ', '.join(all_inaccessible),
        )


def discover(client=None):
    schemas, field_metadata = get_schemas()
    _apply_access_checks(client, schemas, field_metadata)
    catalog = Catalog([])

    for stream_name, schema_dict in schemas.items():
        schema = Schema.from_dict(schema_dict)
        mdata = field_metadata[stream_name]
        stream_metadata = STREAMS.get(stream_name, {})

        catalog.streams.append(CatalogEntry(
            stream=stream_name,
            tap_stream_id=stream_name,
            key_properties=stream_metadata['key_properties'],
            schema=schema,
            metadata=mdata
        ))

    return catalog
