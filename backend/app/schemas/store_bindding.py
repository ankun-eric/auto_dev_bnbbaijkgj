from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ProductStoreBindRequest(BaseModel):
    store_ids: List[int]


class ProductStoreResponse(BaseModel):
    store_id: int
    store_name: str
    store_code: str
    address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class StoreRecommendResponse(BaseModel):
    id: int
    store_name: str
    store_code: str
    address: Optional[str] = None
    match_type: str

    model_config = ConfigDict(from_attributes=True)


class BusinessScopeUpdate(BaseModel):
    business_scope: List[int]
