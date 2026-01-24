**Copernicus Backend (Volcano Monitoring)**

I developed a lightweight Copernicus Data Space backend service that automates volcano monitoring using Sentinel-2 imagery.

The system works with a predefined list of volcano AOIs (stored as GeoJSON polygons). On a daily basis it:

searches the Copernicus Catalog for the most recent Sentinel-2 acquisitions (typically within the last 2 days, with an optional cloud cover filter),

generates false-color composites via the Copernicus Process API,

saves the resulting PNG images and serves them via HTTP so they can be easily loaded into QGIS.

Tech stack / software

Python + FastAPI (REST API backend)

httpx and asyncio for asynchronous processing and batch requests

Static file hosting using FastAPI StaticFiles

Daily automation via a Python job script (requests, retry logic, optional **SMTP email reporting`)

Configuration through environment variables (Copernicus OAuth credentials and job parameters)

Postman is used for testing and validating API endpoints during development (AOIs, scene search, false-color generation)

API functionality

AOI listing and metadata (/aois)

Latest Sentinel-2 scene discovery per AOI (/aois/{id}/latest-scene)

False-color image generation and retrieval (/aois/{id}/latest-fc, /aois/{id}/fc.png)

Batch processing for all AOIs (/latest-scenes, /latest-fc-all)

The backend is designed as a data provider for a future QGIS plugin, allowing users to access up-to-date, preprocessed satellite imagery for multiple volcanoes without manually working in the Copernicus Browser.
