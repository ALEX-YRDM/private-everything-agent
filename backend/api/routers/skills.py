from fastapi import APIRouter, Depends

from ..deps import get_agent

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/system")
async def list_system_skills(agent=Depends(get_agent)):
    skills_loader = agent.context.skills
    all_skills = skills_loader.list_system_skills(filter_unavailable=False)
    return {
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "available": skills_loader._check_requirements(s),
                "requires_bins": s.requires_bins,
                "requires_env": s.requires_env,
            }
            for s in all_skills
        ]
    }


@router.get("/user")
async def list_user_skills(agent=Depends(get_agent)):
    skills_loader = agent.context.skills
    user_skills = skills_loader.list_user_skills()
    return {
        "skills": [
            {"name": s.name, "description": s.description, "path": str(s.path)}
            for s in user_skills
        ]
    }