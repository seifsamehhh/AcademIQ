# setup.py
import subprocess
import sys

def install_dependencies():
    """Install all required dependencies"""
    dependencies = [
        'PyPDF2',
        'python-pptx',
        'torch',
        'transformers',
        'nltk',
        'sentence-transformers',
        'scikit-learn',
        'rank_bm25',
        'networkx',
        'pillow'
    ]
    
    for package in dependencies:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    
    # Download NLTK data
    import nltk
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('wordnet')
    nltk.download('averaged_perceptron_tagger')
    
    print("\n✅ All dependencies installed successfully!")

if __name__ == "__main__":
    install_dependencies()