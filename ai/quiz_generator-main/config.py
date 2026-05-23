import os
import re
import json
import warnings
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import argparse
import subprocess
import sys
import random

warnings.filterwarnings('ignore')


def install_packages():
    """Install required packages"""
    required_packages = [
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
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])


install_packages()


import PyPDF2
from pptx import Presentation
import torch
import transformers
import nltk
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi
import networkx as nx
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.stem import WordNetLemmatizer
from nltk import pos_tag

# Download NLTK data because python sucks
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('wordnet', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
except:
    pass