from pydantic import BaseModel, validator, Field
from typing import List, Dict, Optional
import validators

"""
 Input data organized with Pydantic library
 Model based approach
"""

class FetchDataBase(BaseModel):
    """
    Base class for input data
    """
    method: str = "GET"
    retries: int = Field(3, description="number of retries", ge=0, le=99)
    cookies: Dict[str, str] = None
    params: Dict[str, str] = None
    headers: Dict[str, str] = None
    user_agent: Optional[str] = None
    no_proxy: bool = False
    use_cache: bool = False
    timeout: int = 60

    @validator("method")
    def method_validator(cls, method: str):
        if not method.upper() in ['GET', 'POST']:
            raise ValueError("Input proper HTTP Method: GET or POST")
        return method

    @validator("timeout")
    def timeout_validator(cls, timeout: int):
        if timeout <= 0:
            raise ValueError("Input positive value for timeout")
        return timeout


class FetchOneUrl(FetchDataBase):
    """
    Class for single input url
    """
    url: str

    @validator("url")
    def urls_validator(cls, url: str):
        if not validators.url(url):
            raise ValueError(f"Not valid URL address: {url}")
        return url


class FetchManyUrl(FetchDataBase):
    """
    Class for multiple urls
    """
    urls: List[str] = []

    @validator("urls")
    def urls_validator(cls, urls: List[str]):
        if len(urls) == 0:
            raise ValueError("Input URL list")
        if len(urls) > 1000:
            raise ValueError("Pass max 1000 URLs")
        for url in urls:
            if not validators.url(url):
                raise ValueError(f"Not valid URL address: {url}")
        return urls
