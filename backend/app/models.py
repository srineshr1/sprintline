from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.utcnow()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brief: Mapped[str] = mapped_column(Text, default="")
    goals: Mapped[str] = mapped_column(Text, default="[]")  # JSON list as string
    constraints: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    epics: Mapped[list[Epic]] = relationship(
        "Epic", back_populates="project", cascade="all, delete-orphan"
    )
    sprints: Mapped[list[Sprint]] = relationship(
        "Sprint", back_populates="project", cascade="all, delete-orphan"
    )
    activities: Mapped[list[Activity]] = relationship(
        "Activity", back_populates="project", cascade="all, delete-orphan"
    )


class Epic(Base):
    __tablename__ = "epics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped[Project] = relationship("Project", back_populates="epics")
    stories: Mapped[list[Story]] = relationship(
        "Story", back_populates="epic", cascade="all, delete-orphan"
    )


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    epic_id: Mapped[int] = mapped_column(ForeignKey("epics.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    acceptance_criteria: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    points: Mapped[int] = mapped_column(Integer, default=3)
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # high/medium/low
    status: Mapped[str] = mapped_column(String(30), default="todo")  # todo/in_progress/done
    rationale: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer, default=0)

    epic: Mapped[Epic] = relationship("Epic", back_populates="stories")
    sprint_items: Mapped[list[SprintItem]] = relationship(
        "SprintItem", back_populates="story", cascade="all, delete-orphan"
    )


class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[str] = mapped_column(Text, default="")
    start: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    end: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    capacity_points: Mapped[int] = mapped_column(Integer, default=20)
    status: Mapped[str] = mapped_column(String(20), default="planned")  # planned/active/closed

    project: Mapped[Project] = relationship("Project", back_populates="sprints")
    items: Mapped[list[SprintItem]] = relationship(
        "SprintItem", back_populates="sprint", cascade="all, delete-orphan"
    )


class SprintItem(Base):
    __tablename__ = "sprint_items"
    __table_args__ = (UniqueConstraint("sprint_id", "story_id", name="uq_sprint_story"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sprint_id: Mapped[int] = mapped_column(ForeignKey("sprints.id"), nullable=False)
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id"), nullable=False)

    sprint: Mapped[Sprint] = relationship("Sprint", back_populates="items")
    story: Mapped[Story] = relationship("Story", back_populates="sprint_items")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped[Project] = relationship("Project", back_populates="activities")
