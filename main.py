#!/usr/bin/env python3
# MaxMind GeoIP API Server - Developed by acidvegas in Python (https://git.acid.vegas/maxmind-server)
# maxmind-server/main.py

import asyncio
import ipaddress
import logging
import os
import tarfile
from contextlib import asynccontextmanager
from pathlib    import Path

try:
	import aiohttp
except ImportError:
	raise ImportError('missing aiohttp library (pip install aiohttp)')

try:
	import aiofiles
except ImportError:
	raise ImportError('missing aiofiles library (pip install aiofiles)')

try:
	from fastapi import FastAPI, HTTPException, Request
except ImportError:
	raise ImportError('missing fastapi library (pip install fastapi)')

try:
	from geoip2.database import Reader
except ImportError:
	raise ImportError('missing geoip2 library (pip install geoip2)')

# Load environment variables if .env file exists (otherwise set by Docker -e flags)
if os.path.exists('.env'):
	try:
		from dotenv import load_dotenv
	except ImportError:
		raise ImportError('missing python-dotenv library (pip install python-dotenv)')
	else:
		load_dotenv()

# MaxMind configuration (sensitive data from .env)
MAXMIND_LICENSE_KEY = os.getenv('MAXMIND_LICENSE_KEY')

# Paths
BASE_DIR    = Path(__file__).parent
ASSETS_DIR  = BASE_DIR / 'assets'
DB_PATH     = ASSETS_DIR / 'GeoLite2-City.mmdb'
ASN_DB_PATH = ASSETS_DIR / 'GeoLite2-ASN.mmdb'

# Update interval (in seconds)
UPDATE_INTERVAL = 86400 # 24 hours

# Download timeout (in seconds), a hung connection would otherwise stop all future updates
DOWNLOAD_TIMEOUT = 300

# Long lived database readers, reopened after every update
readers = {'city': None, 'asn': None}

# Create required directories
os.makedirs(ASSETS_DIR, exist_ok=True)


def open_readers():
	'''Open the database readers, replacing any already open'''

	for key, path in (('city', DB_PATH), ('asn', ASN_DB_PATH)):
		if not os.path.exists(path):
			continue
		old = readers[key]
		readers[key] = Reader(path)
		if old:
			old.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
	'''
	Handle startup and shutdown events

	:param app: The FastAPI app instance
	'''

	open_readers()
	task = asyncio.create_task(update_scheduler())
	yield
	task.cancel()
	for reader in readers.values():
		if reader:
			reader.close()


# Initialize FastAPI, with the automatic docs routes disabled so only / and /{ip} are served
app = FastAPI(title='MaxMind GeoIP API', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


async def download_database(edition: str = 'GeoLite2-City') -> bool:
	'''
	Download and update a MaxMind GeoLite2 database

	:param edition: The MaxMind database edition to download
	'''

	try:
		if not MAXMIND_LICENSE_KEY:
			raise ValueError('MaxMind license key not configured')

		url        = f'https://download.maxmind.com/app/geoip_download?edition_id={edition}&suffix=tar.gz&license_key={MAXMIND_LICENSE_KEY}'
		db_archive = ASSETS_DIR / f'{edition}.tar.gz'

		timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
		async with aiohttp.ClientSession(timeout=timeout) as session:
			async with session.get(url) as response:
				if response.status != 200:
					raise ValueError(f'Failed to download {edition} database (HTTP {response.status})')

				async with aiofiles.open(db_archive, 'wb') as f:
					async for chunk in response.content.iter_chunked(65536):
						await f.write(chunk)

		with tarfile.open(db_archive, 'r:gz') as tar:
			mmdb_file = next((m for m in tar.getmembers() if m.name.endswith('.mmdb')), None)
			if not mmdb_file:
				raise ValueError(f'No .mmdb file found in {edition} archive')

			mmdb_file.name = os.path.basename(mmdb_file.name) # Drop the versioned directory so it lands as assets/<edition>.mmdb
			tar.extract(mmdb_file, ASSETS_DIR, filter='data')

		os.remove(db_archive)

		logging.info(f'Successfully updated {edition} database')
		return True

	except Exception as e:
		logging.error(f'Error updating {edition} database: {e}')
		return False


async def update_scheduler():
	'''Schedule database updates every 24 hours'''

	while True:
		await download_database('GeoLite2-City')
		await download_database('GeoLite2-ASN')
		open_readers()
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


def get_asn_info(ip_address: str) -> dict:
	'''
	Get ASN information for an IP address

	:param ip_address: The IP address to lookup
	'''

	try:
		if not readers['asn']:
			return {}

		response = readers['asn'].asn(ip_address)

		return {
			'number'       : int(response.autonomous_system_number) if response.autonomous_system_number else None,
			'organization' : str(response.autonomous_system_organization) if response.autonomous_system_organization else None
		}
	except Exception as e:
		logging.debug(f'Error getting ASN info: {e}')
		return {}


@app.get('/')
async def lookup_client_ip(request: Request) -> dict:
	'''
	Lookup location data for the client's IP address

	:param request: The request object
	'''

	if request.headers.get('X-Real-IP'):
		client_ip = request.headers.get('X-Real-IP')
	elif request.headers.get('X-Forwarded-For'):
		client_ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
	else:
		client_ip = request.client.host

	return await lookup_ip(client_ip)


@app.get('/{ip_address}')
async def lookup_ip(ip_address: str) -> dict:
	'''
	Lookup location data for an IP address

	:param ip_address: The IP address to lookup
	'''

	if not validate_ip(ip_address):
		raise HTTPException(status_code=400, detail='Invalid IP address')

	if not readers['city']:
		raise HTTPException(status_code=503, detail='Database not available')

	try:
		response = readers['city'].city(ip_address)
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))

	asn_info = get_asn_info(ip_address)

	result = {
		'ip'  : ip_address,
		'asn' : asn_info if asn_info else None,
		'location': {
			'latitude'        : float(response.location.latitude) if response.location and response.location.latitude else None,
			'longitude'       : float(response.location.longitude) if response.location and response.location.longitude else None,
			'accuracy_radius' : int(response.location.accuracy_radius) if response.location and response.location.accuracy_radius else None,
			'time_zone'       : str(response.location.time_zone) if response.location and response.location.time_zone else None
		},
		'city': {
			'name'       : str(response.city.name) if response.city and response.city.name else None,
			'geoname_id' : int(response.city.geoname_id) if response.city and response.city.geoname_id else None
		},
		'postal': {
			'code': str(response.postal.code) if response.postal and response.postal.code else None
		},
		'continent': {
			'code'       : str(response.continent.code) if response.continent and response.continent.code else None,
			'geoname_id' : int(response.continent.geoname_id) if response.continent and response.continent.geoname_id else None,
			'name'       : str(response.continent.name) if response.continent and response.continent.name else None
		},
		'country': {
			'iso_code'             : str(response.country.iso_code) if response.country and response.country.iso_code else None,
			'geoname_id'           : int(response.country.geoname_id) if response.country and response.country.geoname_id else None,
			'name'                 : str(response.country.name) if response.country and response.country.name else None,
			'is_in_european_union' : bool(response.country.is_in_european_union) if response.country and hasattr(response.country, 'is_in_european_union') else None
		},
		'registered_country': {
			'iso_code'             : str(response.registered_country.iso_code) if response.registered_country and response.registered_country.iso_code else None,
			'geoname_id'           : int(response.registered_country.geoname_id) if response.registered_country and response.registered_country.geoname_id else None,
			'name'                 : str(response.registered_country.name) if response.registered_country and response.registered_country.name else None,
			'is_in_european_union' : bool(response.registered_country.is_in_european_union) if response.registered_country and hasattr(response.registered_country, 'is_in_european_union') else None
		},
		'traits': {
			'is_anonymous_proxy'    : bool(response.traits.is_anonymous_proxy) if response.traits and hasattr(response.traits, 'is_anonymous_proxy') else None,
			'is_satellite_provider' : bool(response.traits.is_satellite_provider) if response.traits and hasattr(response.traits, 'is_satellite_provider') else None
		},
		'subdivisions': []
	}

	if response.subdivisions:
		for subdivision in response.subdivisions:
			result['subdivisions'].append({
				'iso_code'   : str(subdivision.iso_code) if subdivision.iso_code else None,
				'geoname_id' : int(subdivision.geoname_id) if subdivision.geoname_id else None,
				'name'       : str(subdivision.name) if subdivision.name else None
			})

	# Remove any empty nested dictionaries
	result = {k: v for k, v in result.items() if v is not None and (not isinstance(v, dict) or any(v.values()))}
	for key in list(result.keys()):
		if isinstance(result[key], dict):
			result[key] = {k: v for k, v in result[key].items() if v is not None}
			if not result[key]:
				del result[key]

	return result


if __name__ == '__main__':
	import uvicorn

	# Configure logging
	logging.basicConfig(format = '%(asctime)s - %(levelname)s - %(message)s', level = logging.INFO)

	uvicorn.run(app, host='0.0.0.0', port=8000)
