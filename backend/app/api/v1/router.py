from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    vehicles,
    claims,
    assessments,
    documents,
    chatbot,
    service_center,
    service_centers,
)


api_router = APIRouter()


# ============================================================
# AUTHENTICATION
# ============================================================

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)


# ============================================================
# USERS
# ============================================================

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"],
)


# ============================================================
# VEHICLES
# ============================================================

api_router.include_router(
    vehicles.router,
    prefix="/vehicles",
    tags=["Vehicles"],
)


# ============================================================
# CLAIMS
# ============================================================

api_router.include_router(
    claims.router,
    prefix="/claims",
    tags=["Claims"],
)


# ============================================================
# AI ASSESSMENT + CLAIM PACKAGE
# ============================================================

api_router.include_router(
    assessments.router,
    prefix="/assessments",
    tags=["AI Assessment & Claim Package"],
)


# ============================================================
# DOCUMENTS / EVIDENCE
# ============================================================

api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Documents & Evidence"],
)


# ============================================================
# RAG CHATBOT
# ============================================================

api_router.include_router(
    chatbot.router,
    prefix="/chatbot",
    tags=["RAG Chatbot"],
)


# ============================================================
# SERVICE CENTER
# ============================================================

api_router.include_router(
    service_center.router,
    prefix="/service-center",
    tags=["Service Center"],
)

api_router.include_router(
    service_centers.router,
    prefix="/service-centers",
    tags=["Service Center Management"],
)
