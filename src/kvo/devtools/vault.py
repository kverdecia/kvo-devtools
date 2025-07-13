from typing import Any
from http import HTTPStatus
from urllib.parse import urljoin
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx

from pydantic import BaseModel, Field, HttpUrl, SecretStr, FilePath


class VaultSecretNotFoundError(LookupError):
    pass


class VaultClient(BaseModel):
    url: HttpUrl = Field(..., frozen=True)
    role_name: str = Field(..., frozen=True)
    role_id: SecretStr = Field(..., frozen=True)
    secret_id: SecretStr = Field(..., frozen=True)
    verify_root_ca: FilePath | None = Field(None, frozen=True)

    def _urljoin(self, path: str) -> HttpUrl:
        result = urljoin(str(self.url), path)
        return HttpUrl(result)

    @property
    def login_url(self) -> HttpUrl:
        return self._urljoin(f'/v1/auth/{self.role_name}/login')

    @asynccontextmanager
    async def get_client(self) -> AsyncIterator[httpx.AsyncClient]:
        params: dict[str, Any] = {}
        if self.verify_root_ca:
            params['verify'] = str(self.verify_root_ca)
        async with httpx.AsyncClient(**params) as client:
            yield client

    async def get_token(self) -> SecretStr:
        body = {
            'role_id': self.role_id.get_secret_value(),
            'secret_id': self.secret_id.get_secret_value(),
        }
        async with self.get_client() as client:
            response = await client.post(str(self.login_url), json=body, timeout=30)
            response.raise_for_status()
            response_json = response.json()
            return SecretStr(response_json['auth']['client_token'])

    @property
    def list_secrets_url(self) -> HttpUrl:
        return self._urljoin('/v1/sys/mounts')

    def secrets_url(self, path) -> HttpUrl:
        return self._urljoin(f'/v1/{path}')

    async def get_secrets(self, path: str, token: SecretStr | None = None) -> dict[str, Any]:
        if token is None:
            token = await self.get_token()
        async with self.get_client() as client:
            headers = {
                'X-Vault-Token': token.get_secret_value()
            }
            response = await client.get(str(self.secrets_url(path)), headers=headers, timeout=30)
            if response.status_code == HTTPStatus.NOT_FOUND:
                raise VaultSecretNotFoundError(path)
            response.raise_for_status()
            return response.json()['data']['data']
