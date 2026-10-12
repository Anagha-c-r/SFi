from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.datasets.registry import all_datasets, get_dataset
from app.deps import current_user
from app.services.payload import template_csv

router = APIRouter(prefix="/api/datasets", tags=["datasets"], dependencies=[Depends(current_user)])


@router.get("")
def list_datasets():
    return [d.to_summary() for d in all_datasets().values()]


@router.get("/{code}")
def dataset_detail(code: str):
    d = get_dataset(code)
    if d is None:
        raise HTTPException(404, "Dataset not found.")
    return d.to_detail()


@router.get("/{code}/template.csv")
def dataset_template(code: str):
    d = get_dataset(code)
    if d is None:
        raise HTTPException(404, "Dataset not found.")
    return Response(template_csv(d), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{d.code}_template.csv"'})
