import singer
from singer.catalog import Catalog, CatalogEntry, Schema

from tap_saasoptics.client import SaaSOpticsForbiddenError
from tap_saasoptics.schema import STREAMS, get_schemas

LOGGER = singer.get_logger()


def _check_stream_access(client, stream_name, stream_config):
    path = stream_config.get('path', stream_name)
    client.get(path, endpoint=f'discover:{stream_name}')


def _apply_access_checks(client, streams):
    if client is None:
        return streams

    accessible = []
    inaccessible = []

    for stream_name, stream_config in streams:
        try:
            _check_stream_access(client, stream_name, stream_config)
            accessible.append((stream_name, stream_config))
        except SaaSOpticsForbiddenError as exc:
            LOGGER.warning(
                "Permission Error: Stream '%s' - %s",
                stream_name,
                exc,
            )
            inaccessible.append(stream_name)

    if inaccessible:
        LOGGER.warning(
            'Unauthorized streams excluded from catalog: %s',
            ', '.join(inaccessible)
        )

    if not accessible:
        raise SaaSOpticsForbiddenError(
            'No streams are accessible. Verify API permissions for the configured token.'
        )

    return accessible


def discover(client=None):
    schemas, field_metadata = get_schemas()
    catalog = Catalog([])

    stream_items = list(STREAMS.items())
    for stream_name, stream_metadata in _apply_access_checks(client, stream_items):
        schema = Schema.from_dict(schemas[stream_name])
        mdata = field_metadata[stream_name]

        catalog.streams.append(CatalogEntry(
            stream=stream_name,
            tap_stream_id=stream_name,
            key_properties=stream_metadata['key_properties'],
            schema=schema,
            metadata=mdata
        ))

    return catalog
