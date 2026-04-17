from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
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
@app.put("/utilisateurs/{user_id}")
def mettre_a_jour_solde(user_id: int, nouveau_solde: float, db: Session = Depends(get_db)):
    # Vérification que le solde n'est pas négatif (règle bancaire)
    if nouveau_solde < 0:
        raise HTTPException(status_code=400, detail="Le solde ne peut pas être négatif")

    # Recherche de l'utilisateur
    utilisateur = db.query(UtilisateurDB).filter(UtilisateurDB.id == user_id).first()
    
    if not utilisateur:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    # Mise à jour du champ
    utilisateur.solde = nouveau_solde
    db.commit() # On enregistre la modification sur le cloud Neon
    db.refresh(utilisateur) # On récupère les données à jour
    
    return {"message": "Solde mis à jour sur Neon", "user": utilisateur}