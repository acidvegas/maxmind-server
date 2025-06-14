#!/usr/bin/env python3
# MaxMind GeoIP API Server - Developed by acidvegas in Python (https://git.acid.vegas/maxmind-server)
# maxmind-server/main.py

import asyncio
import ipaddress
import logging
import os
import shutil
import tarfile

from contextlib import asynccontextmanager

try:
    import aiohttp
except ImportError:
    raise ImportError('missing aiohttp library (pip install aiohttp)')

try:
    import aiofiles
except ImportError:
    raise ImportError('missing aiofiles library (pip install aiofiles)')

try:
    from fastapi           import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse
except ImportError:
    raise ImportError('missing fastapi library (pip install fastapi)')

try:
    from geoip2.database import Reader
except ImportError:
    raise ImportError('missing geoip2 library (pip install geoip2)')

from config import HOST, PORT, DB_PATH, UPDATE_INTERVAL, MAXMIND_LICENSE_KEY, BASE_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    '''
    Handle startup and shutdown events
    
    :param app: The FastAPI app instance
    '''
    asyncio.create_task(update_scheduler())
    yield


# Initialize FastAPI
app = FastAPI(title='MaxMind GeoIP API', lifespan=lifespan)


async def download_database() -> bool:
    '''Download and update the MaxMind GeoLite2 City database'''

    try:
        if not MAXMIND_LICENSE_KEY:
            raise ValueError('MaxMind license key not configured')

        url = f'https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&suffix=tar.gz&license_key={MAXMIND_LICENSE_KEY}'
        db_archive = BASE_DIR / 'assets/GeoLite2-City.tar.gz'

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail='Failed to download database')
                
                async with aiofiles.open(db_archive, 'wb') as f:
                    await f.write(await response.read())

        with tarfile.open(db_archive, 'r:gz') as tar:
            mmdb_file = next((m for m in tar.getmembers() if m.name.endswith('.mmdb')), None)
            if not mmdb_file:
                raise ValueError('No .mmdb file found in archive')

            tar.extract(mmdb_file, '/tmp')
            temp_db = os.path.join('/tmp', mmdb_file.name)
            shutil.copy2(temp_db, DB_PATH)
            os.remove(temp_db)

        logging.info('Successfully updated MaxMind database')
        return True

    except Exception as e:
        logging.error(f'Error updating database: {e}')
        return False


async def update_scheduler():
    '''Schedule database updates every 24 hours'''

    while True:
        await download_database()
        await asyncio.sleep(UPDATE_INTERVAL)


def validate_ip(ip: str) -> bool:
    '''
    Validate an IP address
    
    :param ip: The IP address to validate
    '''
    
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


@app.get('/')
async def lookup_client_ip(request: Request) -> dict:
    '''
    Lookup location data for the client's IP address

    :param request: The request object
    '''

    if request.headers.get('X-Real-IP'):
        client_ip = request.headers.get('X-Real-IP')
    elif request.headers.get('X-Forwarded-For'):
        client_ip = request.headers.get('X-Forwarded-For')
    else:
        client_ip = request.client.host

    return await lookup_ip(client_ip)


@app.get('/{ip_address}')
async def lookup_ip(ip_address: str) -> dict:
    '''
    Lookup location data for an IP address
    
    :param ip_address: The IP address to lookup
    '''
    try:
        if not validate_ip(ip_address):
            raise HTTPException(status_code=400, detail='Invalid IP address')

        if not os.path.exists(DB_PATH):
            raise HTTPException(status_code=503, detail='Database not available')

        with Reader(DB_PATH) as reader:
            response = reader.city(ip_address)
            
            result = {
                'ip': ip_address,
                'location': {
                    'latitude': float(response.location.latitude) if response.location and response.location.latitude else None,
                    'longitude': float(response.location.longitude) if response.location and response.location.longitude else None,
                    'accuracy_radius': int(response.location.accuracy_radius) if response.location and response.location.accuracy_radius else None,
                    'time_zone': str(response.location.time_zone) if response.location and response.location.time_zone else None
                },
                'city': {
                    'name': str(response.city.name) if response.city and response.city.name else None,
                    'geoname_id': int(response.city.geoname_id) if response.city and response.city.geoname_id else None
                },
                'postal': {
                    'code': str(response.postal.code) if response.postal and response.postal.code else None
                },
                'continent': {
                    'code': str(response.continent.code) if response.continent and response.continent.code else None,
                    'geoname_id': int(response.continent.geoname_id) if response.continent and response.continent.geoname_id else None,
                    'name': str(response.continent.name) if response.continent and response.continent.name else None
                },
                'country': {
                    'iso_code': str(response.country.iso_code) if response.country and response.country.iso_code else None,
                    'geoname_id': int(response.country.geoname_id) if response.country and response.country.geoname_id else None,
                    'name': str(response.country.name) if response.country and response.country.name else None,
                    'is_in_european_union': bool(response.country.is_in_european_union) if response.country and hasattr(response.country, 'is_in_european_union') else None
                },
                'registered_country': {
                    'iso_code': str(response.registered_country.iso_code) if response.registered_country and response.registered_country.iso_code else None,
                    'geoname_id': int(response.registered_country.geoname_id) if response.registered_country and response.registered_country.geoname_id else None,
                    'name': str(response.registered_country.name) if response.registered_country and response.registered_country.name else None,
                    'is_in_european_union': bool(response.registered_country.is_in_european_union) if response.registered_country and hasattr(response.registered_country, 'is_in_european_union') else None
                },
                'traits': {
                    'is_anonymous_proxy': bool(response.traits.is_anonymous_proxy) if response.traits and hasattr(response.traits, 'is_anonymous_proxy') else None,
                    'is_satellite_provider': bool(response.traits.is_satellite_provider) if response.traits and hasattr(response.traits, 'is_satellite_provider') else None
                },
                'subdivisions': []
            }

            if response.subdivisions:
                for subdivision in response.subdivisions:
                    result['subdivisions'].append({
                        'iso_code': str(subdivision.iso_code) if subdivision.iso_code else None,
                        'geoname_id': int(subdivision.geoname_id) if subdivision.geoname_id else None,
                        'name': str(subdivision.name) if subdivision.name else None
                    })

            # Remove any empty nested dictionaries
            result = {k: v for k, v in result.items() if v is not None and (not isinstance(v, dict) or any(v.values()))}
            for key in list(result.keys()):
                if isinstance(result[key], dict):
                    result[key] = {k: v for k, v in result[key].items() if v is not None}
                    if not result[key]:
                        del result[key]

            return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get('/database')
async def download_database_archive():
    '''Download the compressed MaxMind database'''

    db_archive = BASE_DIR / 'assets/GeoLite2-City.tar.gz'

    if not os.path.exists(db_archive):
        raise HTTPException(status_code=404, detail='Database archive not found')

    return FileResponse(db_archive, filename='GeoLite2-City.tar.gz', media_type='application/gzip')



if __name__ == '__main__':
    import uvicorn

    # Configure logging
    logging.basicConfig(format = '%(asctime)s - %(levelname)s - %(message)s', level = logging.INFO)
    
    uvicorn.run(app, host=HOST, port=PORT) 