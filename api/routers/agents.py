from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
import auth

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("", response_model=list[schemas.AgentOut], summary="List all agents")
def list_agents(
    is_active:    Optional[bool] = Query(True),
    search:       Optional[str]  = Query(None, description="Search by name or company"),
    limit:        int = Query(50, ge=1, le=200),
    offset:       int = Query(0,  ge=0),
    db:           Session = Depends(get_db),
    _:            models.User = Depends(auth.get_current_user),
):
    q = db.query(models.Agent)
    if is_active is not None:
        q = q.filter(models.Agent.is_active == is_active)
    if search:
        term = f"%{search}%"
        q = q.filter(
            models.Agent.contact_name.ilike(term) |
            models.Agent.company_name.ilike(term)
        )
    return q.order_by(models.Agent.contact_name).offset(offset).limit(limit).all()


@router.get("/{agent_id}", response_model=schemas.AgentOut, summary="Get agent by ID")
def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    agent = db.query(models.Agent).filter(models.Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.post("", response_model=schemas.AgentOut, status_code=status.HTTP_201_CREATED,
             summary="Register a new agent")
def create_agent(
    payload: schemas.AgentCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    agent = models.Agent(**payload.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.put("/{agent_id}", response_model=schemas.AgentOut, summary="Update agent details")
def update_agent(
    agent_id: int,
    payload: schemas.AgentUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    agent = db.query(models.Agent).filter(models.Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Deactivate an agent (admin only)")
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    agent = db.query(models.Agent).filter(models.Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    agent.is_active = False
    db.commit()
