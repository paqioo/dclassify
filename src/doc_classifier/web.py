from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from .ai import check_ollama_connection, classify_text
from .models import Config
from .parser import extract_text, get_supported_extensions
from .rules import (
    apply_classification,
    classify_by_keywords,
    find_config_file,
    load_config,
    undo_last,
)


def main() -> None:
    st.set_page_config(
        page_title="Doc Classifier",
        page_icon="📂",
        layout="centered",
    )

    st.title("📂 Document Classifier")
    st.caption("Privacy-First, Local-AI Powered Smart Document Organization")

    resolved = find_config_file()
    config = load_config(str(resolved)) if resolved else Config()

    with st.sidebar:
        st.header("Settings")
        ai_model = st.text_input("AI Model", value=config.classification.default_model)
        output_dir = st.text_input("Output Directory", value=".")
        dry_run = st.checkbox("Dry-Run Mode", value=False)
        local_only = st.checkbox("Local-Only (block cloud)", value=True)

        st.divider()
        if st.button("Check AI Connection"):
            with st.spinner("Checking..."):
                ok = check_ollama_connection(ai_model)
            if ok:
                st.success("Model is reachable!")
            else:
                st.error("Cannot reach model. Is Ollama running?")

        st.divider()
        if st.button("Undo Last"):
            op = undo_last()
            if op:
                st.success(f"Undone: {Path(op.target_path).name} -> {Path(op.original_path).name}")
            else:
                st.warning("No operations to undo.")

    exts = sorted(get_supported_extensions())
    uploaded_files = st.file_uploader(
        "Upload document(s)",
        type=[e.lstrip(".") for e in exts],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Upload one or more files to classify.")
        return

    if st.button("Classify & Organize", type="primary"):
        results: list[dict] = []

        progress = st.progress(0, text="Processing...")
        for idx, uploaded in enumerate(uploaded_files):
            progress.progress(
                (idx) / len(uploaded_files),
                text=f"Processing: {uploaded.name}",
            )

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(uploaded.name).suffix
            ) as tmp:
                tmp.write(uploaded.getbuffer())
                tmp_path = tmp.name

            try:
                text = extract_text(tmp_path)

                classification = None
                if text:
                    classification = classify_text(
                        text,
                        model=ai_model,
                        temperature=config.classification.temperature,
                        local_only=local_only,
                    )

                if not classification and config.classification.fallback_keywords:
                    classification = classify_by_keywords(
                        text or "", config.taxonomy, original_name=uploaded.name
                    )
                    operation = apply_classification(
                        tmp_path, classification, config, output_dir=output_dir, dry_run=dry_run
                    )
                    results.append({
                        "file": uploaded.name,
                        "status": "KEYWORD" if operation.action == "move" else "DRY-RUN",
                        "category": classification.main_category,
                        "type": "keyword",
                        "new_name": Path(operation.target_path).name,
                        "title": classification.title,
                        "summary": classification.summary,
                    })
                    continue

                if not classification:
                    results.append(
                        {"file": uploaded.name, "status": "SKIP (AI error)", "category": "-"}
                    )
                    continue

                operation = apply_classification(
                    tmp_path, classification, config, output_dir=output_dir, dry_run=dry_run
                )

                status = "OK" if operation.action == "move" else "DRY-RUN"
                results.append({
                    "file": uploaded.name,
                    "status": status,
                    "category": classification.main_category,
                    "type": classification.document_type,
                    "new_name": Path(operation.target_path).name,
                    "title": classification.title,
                    "summary": classification.summary,
                })
            finally:
                if os.path.exists(tmp_path) and dry_run:
                    os.unlink(tmp_path)

        progress.progress(1.0, text="Done!")

        st.divider()
        st.subheader("Results")

        for r in results:
            if r["status"] in ("OK", "DRY-RUN", "KEYWORD"):
                with st.expander(f"{'✅' if r['status'] == 'OK' else '🔍'} {r['file']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Title:** {r.get('title', '-')}")
                        st.markdown(f"**Category:** {r.get('category', '-')}")
                        st.markdown(f"**Type:** {r.get('type', '-')}")
                    with col2:
                        st.markdown(f"**New Name:** `{r.get('new_name', '-')}`")
                        st.markdown(f"**Status:** {r['status']}")
                    if r.get("summary"):
                        st.caption(r["summary"])
            else:
                st.warning(f"⚠️ {r['file']}: {r['status']}")

        if dry_run:
            st.info("Dry-run mode — no files were moved.")


if __name__ == "__main__":
    main()
