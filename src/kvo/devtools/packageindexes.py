from pydantic import BaseModel, HttpUrl


class PackageIndex(BaseModel):
    name: str
    download_url: HttpUrl
    upload_url: HttpUrl
    insecure_host: bool = False
