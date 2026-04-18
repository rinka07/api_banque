from pydantic import BaseModel, EmailStr, Field
from enum import Enum
from typing import Optional

# Schémas pour l'Utilisateur
class UtilisateurUpdate(BaseModel):
    nom: Optional[str] = Field(None, min_length=2)
    email: Optional[EmailStr] = None
    solde: Optional[float] = Field(None, ge=0)

# Définition des types autorisés
class TypeCompte(str, Enum):
    COURANT = "courant"
    EPARGNE = "epargne"

# Utilisation dans le schéma de création
class CompteCreate(BaseModel):
    type_compte: TypeCompte = Field(..., description="Le type de compte doit être 'courant' ou 'epargne'")
    user_id: int

# Schémas pour la Transaction
class TransactionCreate(BaseModel):
    montant: float = Field(..., ge=100) # Minimum 100 XAF pour éviter les frais inutiles
    compte_id: int
    description: Optional[str] = "Opération bancaire"