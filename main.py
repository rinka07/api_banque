from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional
import uvicorn
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

# --- CONFIGURATION NEON ---
DATABASE_URL = os.environ.get("DATABASE_URL")

# Création du moteur de connexion
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODÈLE DE LA TABLE (SQLAlchemy) ---
class UtilisateurDB(Base):
    __tablename__ = "utilisateurs"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String)
    email = Column(String, unique=True, index=True)
    solde = Column(Float, default=0.0)

# Création automatique de la table sur Neon
Base.metadata.create_all(bind=engine)

# --- SCHÉMA DE DONNÉES (Pydantic) ---
class UtilisateurSchema(BaseModel):
    nom: str = Field(..., min_length=2)
    email: EmailStr
    solde: float = Field(default=0.0, ge=0)

    class Config:
        from_attributes = True # Permet à FastAPI de lire les objets de la base de données

# --- DÉPENDANCE ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- APPLICATION ---
app = FastAPI(
    title="API de gestion des utilisateurs",
    description="Connectée à PostgreSQL sur Neon.tech",
    version="1.0.0"
)

# 1. Le Contrôleur pour AJOUTER un utilisateur
@app.post("/utilisateurs/ajout", status_code=201)
def ajouter_utilisateur(user: UtilisateurSchema, db: Session = Depends(get_db)):
    # Vérification de l'unicité directement dans la base de données
    db_user = db.query(UtilisateurDB).filter(UtilisateurDB.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")
    
    # Création et enregistrement
    nouvel_utilisateur = UtilisateurDB(nom=user.nom, email=user.email, solde=user.solde)
    db.add(nouvel_utilisateur)
    db.commit() # Sauvegarde réelle sur Neon
    db.refresh(nouvel_utilisateur) # Récupère l'ID généré par la base
    
    return {"message": "New user added successfully to Neon !", "data": nouvel_utilisateur}

# 2. Le Contrôleur pour VOIR la liste
@app.get("/utilisateurs/lister")
def lister_utilisateurs(db: Session = Depends(get_db)):
    utilisateurs = db.query(UtilisateurDB).all()
    return utilisateurs

# 4. Le Contrôleur pour SUPPRIMER un utilisateur
@app.delete("/utilisateurs/{user_id}")
def supprimer_utilisateur(user_id: int, db: Session = Depends(get_db)):
    # On recherche l'utilisateur par son ID réel dans la table
    utilisateur = db.query(UtilisateurDB).filter(UtilisateurDB.id == user_id).first()
    
    if not utilisateur:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    # Suppression dans la base de données
    db.delete(utilisateur)
    db.commit() # Très important pour valider la suppression sur Neon
    
    return {"message": f"L'utilisateur {utilisateur.nom} a été supprimé avec succès"}

# 5. Le Contrôleur pour METTRE À JOUR le solde

class UtilisateurUpdate(BaseModel):
    # On utilise Optional pour permettre de ne pas envoyer le champ
    # EmailStr valide automatiquement le format de l'email
    nom: Optional[str] = Field(None, min_length=2)
    email: Optional[EmailStr] = None 
    solde: Optional[float] = Field(None, ge=0) # ge=0 vérifie que le solde est >= 0

@app.patch("/utilisateurs/{user_id}")
def modifier_utilisateur_partiel(user_id: int, obj_update: UtilisateurUpdate, db: Session = Depends(get_db)):
    # 1. Recherche de l'utilisateur
    utilisateur = db.query(UtilisateurDB).filter(UtilisateurDB.id == user_id).first()
    
    if not utilisateur:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    # 2. Conversion en dictionnaire en excluant les champs non envoyés (unset)
    # C'est cette option qui empêche de tout écraser par None
    donnees_maj = obj_update.dict(exclude_unset=True)

    # 3. Vérification si l'email est déjà pris par un autre utilisateur
    if "email" in donnees_maj:
        email_existant = db.query(UtilisateurDB).filter(
            UtilisateurDB.email == donnees_maj["email"], 
            UtilisateurDB.id != user_id
        ).first()
        if email_existant:
            raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")

    # 4. Application des modifications uniquement pour les champs reçus
    for cle, valeur in donnees_maj.items():
        setattr(utilisateur, cle, valeur)

    db.commit()
    db.refresh(utilisateur)
    
    return {
        "message": "Mise à jour partielle réussie",
        "utilisateur": utilisateur
    }