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


class StoreBinddingProductItem(BaseModel):
    id: int
    name: str
    category_name: Optional[str] = None
    sale_price: float
    images: Optional[list] = None
    status: str
    bound_store_count: int


class StoreBinddingStoreItem(BaseModel):
    id: int
    store_name: str
    store_code: str
    status: str
    bound_product_count: int


class ProductStoreCheckItem(BaseModel):
    store_id: int
    store_name: str
    store_code: str
    address: Optional[str] = None
    status: str
    is_bound: bool


class StoreProductCheckItem(BaseModel):
    product_id: int
    name: str
    category_name: Optional[str] = None
    sale_price: float
    images: Optional[list] = None
    status: str
    is_bound: bool


class SingleBindRequest(BaseModel):
    product_id: int
    store_id: int


class BatchBindRequest(BaseModel):
    product_ids: List[int]
    store_id: int


class BatchBindResponse(BaseModel):
    message: str
    success_count: int
    fail_count: int
    failures: List[str] = []


class BoundCountResponse(BaseModel):
    product_id: int
    bound_store_count: int
