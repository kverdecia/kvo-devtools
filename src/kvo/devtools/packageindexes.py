import os

from pydantic import BaseModel, HttpUrl, SecretStr


class PythonPackageIndex(BaseModel):
    package_index: str | None

    @property
    def package_index_varname(self) -> str | None:
        if self.package_index is None:
            return None
        return self.package_index.upper().replace("-", "_")

    @property
    def index_token_varname(self) -> str:
        if self.package_index is None:
            return 'KVO_DEVTOOLS_PYTHON_PACKAGE_INDEX_TOKEN'
        return f'KVO_DEVTOOLS_PYTHON_PACKAGE_INDEX_TOKEN_{self.package_index_varname}'

    @property
    def index_token(self) -> SecretStr | None:
        index_token = os.environ.get(self.index_token_varname)
        if index_token is None:
            return None
        return SecretStr(index_token)

    @property
    def index_url_varname(self) -> str:
        if self.package_index is None:
            return 'KVO_DEVTOOLS_PYTHON_PACKAGE_INDEX_URL'
        return f'KVO_DEVTOOLS_PYTHON_PACKAGE_INDEX_URL_{self.package_index_varname}'

    @property
    def index_url(self) -> HttpUrl | None:
        index_url = os.environ.get(self.index_url_varname)
        if index_url is None:
            return None
        return HttpUrl(index_url)

    @property
    def index_env(self) -> dict[str, str]:
        index_env = {}
        if self.index_url is not None:
            index_env['UV_INDEX'] = str(self.index_url) if self.package_index is None else f'{self.package_index}={self.package_index}'
        if self.index_token is not None:
            index_env[f'UV_INDEX_{self.package_index_varname}_USERNAME'] = '__token__'
            index_env[f'UV_INDEX_{self.package_index_varname}_PASSWORD'] = self.index_token.get_secret_value()
        env = dict(os.environ)
        env.pop('VIRTUAL_ENV', None)
        return {**env, **index_env}

    @property
    def upload_token_varname(self) -> str:
        if self.package_index is None:
            return 'KVO_DEVTOOLS_PYTHON_PACKAGE_UPLOAD_TOKEN'
        return f'KVO_DEVTOOLS_PYTHON_PACKAGE_UPLOAD_TOKEN_{self.package_index_varname}'

    @property
    def upload_token(self) -> SecretStr | None:
        upload_token = os.environ.get(self.upload_token_varname)
        if upload_token is None:
            return None
        return SecretStr(upload_token)

    @property
    def upload_url_varname(self) -> str:
        if self.package_index is None:
            return 'KVO_DEVTOOLS_PYTHON_PACKAGE_UPLOAD_URL'
        return f'KVO_DEVTOOLS_PYTHON_PACKAGE_UPLOAD_URL_{self.package_index_varname}'

    @property
    def upload_url(self) -> HttpUrl | None:
        upload_url = os.environ.get(self.upload_url_varname)
        if upload_url is None:
            return None
        return HttpUrl(upload_url)

    @property
    def upload_env(self) -> dict[str, str]:
        upload_env = {}
        if self.upload_url is not None:
            upload_env['UV_PUBLISH_URL'] = str(self.upload_url)
        if self.upload_token is not None:
            upload_env['UV_PUBLISH_USERNAME'] = '__token__'
            upload_env['UV_PUBLISH_PASSWORD'] = self.upload_token.get_secret_value()
        env = dict(os.environ)
        env.pop('VIRTUAL_ENV', None)
        return {**env, **upload_env}
