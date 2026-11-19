# MaxMind GeoIP API Server

A small FastAPI server that answers GeoIP and ASN lookups from the free MaxMind GeoLite2 City and ASN databases. The databases are downloaded on startup and refreshed every 24 hours.

## Requirements
- Docker
- A free [MaxMind license key](https://www.maxmind.com/en/geolite2/signup)

## Setup
```bash
cp .env.example .env    # then set MAXMIND_LICENSE_KEY
sudo ./setup.sh
```

`setup.sh` builds the image and runs the container as an unprivileged user *(UID 10001)*, with the databases stored in `/opt/container-storage/maxmind`. The API listens on `127.0.0.1:8000`, so put a reverse proxy in front of it to expose it.

## Usage
| Endpoint    | Description                                                                                     |
|-------------|-------------------------------------------------------------------------------------------------|
| `GET /`     | Look up the client's own IP *(uses `X-Real-IP`, then `X-Forwarded-For`, then the peer address)* |
| `GET /{ip}` | Look up any IPv4 or IPv6 address                                                                |

```bash
curl http://127.0.0.1:8000/8.8.8.8
```

Example response:
```json
{
  "ip": "8.8.8.8",
  "asn": {"number": 15169, "organization": "GOOGLE"},
  "location": {"latitude": 37.751, "longitude": -97.822, "accuracy_radius": 1000, "time_zone": "America/Chicago"},
  "continent": {"code": "NA", "geoname_id": 6255149, "name": "North America"},
  "country": {"iso_code": "US", "geoname_id": 6252001, "name": "United States", "is_in_european_union": false},
  "registered_country": {"iso_code": "US", "geoname_id": 6252001, "name": "United States", "is_in_european_union": false},
  "subdivisions": []
}
```

Fields with no data are left out of the response.

| Status | Meaning                        |
|--------|--------------------------------|
| `400`  | Invalid IP address             |
| `404`  | IP address not in the database |
| `503`  | Database not downloaded yet    |

---

###### Mirrors: [SuperNETs](https://git.supernets.org/acidvegas/) • [GitHub](https://github.com/acidvegas/) • [GitLab](https://gitlab.com/acidvegas/) • [Codeberg](https://codeberg.org/acidvegas/)
