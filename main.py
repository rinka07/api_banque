from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from enum import Enum
import random
from typing import Optional, List
import os
import uvicorn

# --- CONFIGURATION BASE DE DONNÉES ---
DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- ÉNUMÉRATIONS ---
class TypeCompte(str, Enum):
    COURANT = "courant"
    EPARGNE = "epargne"

# --- MODÈLES SQLALCHEMY ---
class UtilisateurDB(Base):
    __tablename__ = "utilisateurs"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String)
    email = Column(String, unique=True, index=True)
    solde = Column(Float, default=0.0)
    # Relation : un utilisateur peut avoir plusieurs comptes
    comptes = relationship("CompteDB", back_populates="proprietaire", cascade="all, delete-orphan")

class CompteDB(Base):
    __tablename__ = "comptes"
    id = Column(Integer, primary_key=True, index=True)
    numero_compte = Column(String, unique=True)
    type = Column(SQLEnum(TypeCompte), default=TypeCompte.COURANT)
    solde = Column(Float, default=0.0)
    user_id = Column(Integer, ForeignKey("utilisateurs.id"))
    # Relation : chaque compte appartient à un propriétaire
    proprietaire = relationship("UtilisateurDB", back_populates="comptes")
    transactions = relationship("TransactionDB", back_populates="compte")

class TransactionDB(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    montant = Column(Float)
    type = Column(String) # DEPOT ou RETRAIT
    reference = Column(String, unique=True)
    description = Column(String)
    compte_id = Column(Integer, ForeignKey("comptes.id"))
    compte = relationship("CompteDB", back_populates="transactions")

# Création des tables sur Neon
Base.metadata.create_all(bind=engine)

# --- SCHÉMAS PYDANTIC ---
class UtilisateurSchema(BaseModel):
    nom: str = Field(..., min_length=2)
    email: EmailStr
    solde: float = Field(default=0.0, ge=0)

class UtilisateurUpdate(BaseModel):
    nom: Optional[str] = Field(None, min_length=2)
    email: Optional[EmailStr] = None
    solde: Optional[float] = Field(None, ge=0)

class CompteCreate(BaseModel):
    type_compte: TypeCompte # L'utilisateur DOIT choisir parmi l'Enum
    user_id: int

class TransactionCreate(BaseModel):
    montant: float = Field(..., ge=100)
    compte_id: int
    description: Optional[str] = "Opération bancaire"

# --- DÉPENDANCE ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- APPLICATION ---
app = FastAPI(title="API Banque Pro - Rinka")

# --- ROUTES UTILISATEURS ---

@app.post("/utilisateurs/ajout", status_code=201)
def ajouter_utilisateur(user: UtilisateurSchema, db: Session = Depends(get_db)):
    db_user = db.query(UtilisateurDB).filter(UtilisateurDB.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")
    nouvel_utilisateur = UtilisateurDB(nom=user.nom, email=user.email, solde=user.solde)
    db.add(nouvel_utilisateur)
    db.commit()
    db.refresh(nouvel_utilisateur)
    return nouvel_utilisateur

@app.get("/utilisateurs/lister")
def lister_utilisateurs(db: Session = Depends(get_db)):
    return db.query(UtilisateurDB).all()

@app.patch("/utilisateurs/{user_id}")
def modifier_utilisateur_partiel(user_id: int, obj_update: UtilisateurUpdate, db: Session = Depends(get_db)):
    utilisateur = db.query(UtilisateurDB).filter(UtilisateurDB.id == user_id).first()
    if not utilisateur:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    donnees_maj = obj_update.dict(exclude_unset=True)
    for cle, valeur in donnees_maj.items():
        setattr(utilisateur, cle, valeur)
    db.commit()
    db.refresh(utilisateur)
    return utilisateur

# --- ROUTES COMPTES ---

@app.post("/comptes/", status_code=201)
def creer_compte(compte_data: CompteCreate, db: Session = Depends(get_db)):
    user = db.query(UtilisateurDB).filter(UtilisateurDB.id == compte_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur parent introuvable")
    
    num_compte = f"CM23-{random.randint(1000, 9999)}-{random.randint(10**7, 10**8-1)}"
    nouveau_compte = CompteDB(
        numero_compte=num_compte, 
        type=compte_data.type_compte, 
        solde=0.0, 
        user_id=compte_data.user_id
    )
    db.add(nouveau_compte)
    db.commit()
    db.refresh(nouveau_compte)
    return nouveau_compte

# --- ROUTES TRANSACTIONS ---

@app.post("/transactions/{type_op}")
def effectuer_transaction(type_op: str, trans: TransactionCreate, db: Session = Depends(get_db)):
    compte = db.query(CompteDB).filter(CompteDB.id == trans.compte_id).first()
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    
    if type_op.lower() == "retrait":
        if compte.solde < trans.montant:
            raise HTTPException(status_code=400, detail="Solde insuffisant")
        compte.solde -= trans.montant
    elif type_op.lower() == "depot":
        compte.solde += trans.montant
    else:
        raise HTTPException(status_code=400, detail="Action invalide (depot/retrait)")

    historique = TransactionDB(
        montant=trans.montant, 
        type=type_op.upper(), 
        compte_id=compte.id, 
        description=trans.description, 
        reference=f"REF-{random.randint(10**8, 10**9)}"
    )
    db.add(historique)
    db.commit()
    db.refresh(compte)
    return {"message": "Transaction effectuée", "nouveau_solde": compte.solde}

# --- DÉMARRAGE ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)