from pydantic import BaseModel, EmailStr, Field
from typing import Optional

# Schémas pour l'Utilisateur
class UtilisateurUpdate(BaseModel):
    nom: Optional[str] = Field(None, min_length=2)
    email: Optional[EmailStr] = None
    solde: Optional[float] = Field(None, ge=0)

# Schémas pour le Compte
class CompteCreate(BaseModel):
    type_compte: str = Field(..., example="courant") # courant ou epargne
    user_id: int

# Schémas pour la Transaction
class TransactionCreate(BaseModel):
    montant: float = Field(..., ge=100) # Minimum 100 XAF pour éviter les frais inutiles
    compte_id: int
    description: Optional[str] = "Opération bancaire"