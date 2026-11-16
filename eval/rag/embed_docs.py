"""장소 글을 임베딩해 캐시한다. 중간에 멈추면 다시 돌리면 이어서 받는다.

cd ai
python ../eval/rag/embed_docs.py --model bge-m3 --mode name_cat_body
"""

import argparse

from corpus import DEFAULT_CORPUS, embed_docs, load_corpus

from app.rag.text import MODES

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--mode", default="name_cat_body", choices=MODES)
ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
args = ap.parse_args()
embed_docs(load_corpus(args.corpus), args.model, args.mode)
