"""
4K AI WORKSTATION - Usage & Analytics Tracker (Kullanım ve Tasarruf Takip Motoru)
Kullanıcının 5 Saatlik (5h) ve Haftalık (7g) model, CLI ve alt ajan kullanımlarını,
conversations/*.db SQLite gen_metadata verileriyle gerçek alt model bazında (Argon, Flash 3.8, Lite, Claude, Codex),
ücretli modelleri sabit standart sırada ve ücretsiz modelleri en çok kullanılandan aşağıya doğru dinamik sıralı olarak takip eder.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# Referans Limitleri
REF_FREE_LIMIT_5H = 400_000       # 400K Token (Claude 5s Uzman Kotası Referansı)
REF_FREE_LIMIT_WEEKLY = 2_000_000 # 2.00M Token (Claude Haftalık Uzman Kotası Referansı)


def format_tokens(n: int) -> str:
    """Token sayısını okunaklı bir stringe dönüştürür (örn. 52.0K, 1.45M)."""
    val = max(0, int(n))
    if val >= 1_000_000:
        return f"{val / 1_000_000:.2f}M"
    elif val >= 1_000:
        return f"{val / 1_000:.1f}K"
    return str(val)


def render_model_quota_bar(tokens: int, limit: int, is_free: bool = False, width: int = 20) -> str:
    """
    Her modelin kendi kotasına veya ücretsiz modeller için referans uzman kotasına göre
    görsel grafik barı üretir.
    Ücretli modellerde yüzde ASLA %100'ü geçemez ve 🔥 alamaz.
    Yalnızca ücretsiz modellerde limit aşıldığında (%100+) yanına 🔥 eklenir.
    """
    if limit <= 0:
        raw_pct = 0.0
    else:
        raw_pct = round((tokens / limit) * 100.0, 1)

    if not is_free:
        pct = min(100.0, max(0.0, raw_pct))
        filled = min(width, int(round((pct / 100.0) * width)))
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] %{pct:.1f} ({format_tokens(tokens)} / {format_tokens(limit)})"
    else:
        pct = max(0.0, raw_pct)
        filled = min(width, int(round((min(100.0, pct) / 100.0) * width)))
        bar = "█" * filled + "░" * (width - filled)
        fire = " 🔥" if pct >= 100.0 else ""
        return f"[{bar}]{fire} %{pct:.1f} ({format_tokens(tokens)} Token)"


def normalize_agent_name(name: str) -> str:
    """
    Teknik alt ajan mesajlarını ve rollerini ana uzman ajan kategorilerine gruplar.
    """
    n = (name or "").lower()
    if any(k in n for k in ["ui", "arayüz", "kontrol paneli", "dashboard"]):
        return "🎨 UI & Kontrol Paneli Uzmanı"
    if any(k in n for k in ["test", "kalite", "doğrulama"]):
        return "🧪 Test & Kalite Güvence Uzmanı"
    if any(k in n for k in ["dokümantasyon", "marka", "belge", "kural"]):
        return "📝 Dokümantasyon & Marka Uzmanı"
    if any(k in n for k in ["çekirdek", "api", "workspace", "builder", "core"]):
        return "⚙️ Çekirdek & API Uzmanı"
    if any(k in n for k in ["kullanım", "analitik", "usage", "tracker"]):
        return "📊 Kullanım & Analitik Motoru Uzmanı"
    if any(k in n for k in ["antigravity", "özelleştirme", "skill", "yapılandırma"]):
        return "🧠 Antigravity Entegrasyon Uzmanı"
    if any(k in n for k in ["terminal", "cli"]):
        return "💻 Terminal & CLI Ajanı"
    return "⚡ Nexus Worker (Genel Görev İşçisi)"


class UsageTracker:
    """
    Yerel 4K AI Workstation ve Antigravity orkestrasyon motorunun kullanım verilerini toplayıp
    görsel ve finansal tasarruf raporlarına dönüştüren analitik motoru.
    """

    # Sağlayıcı / Firma Tanımları
    PROVIDERS = {
        "anthropic": {"name": "Anthropic", "label": "🟣 Anthropic (Claude)", "color": "🟣", "default_limit_5h": 400_000, "default_limit_w": 2_000_000},
        "openai": {"name": "OpenAI", "label": "🟢 OpenAI", "color": "🟢", "default_limit_5h": 800_000, "default_limit_w": 4_000_000},
        "google": {"name": "Google", "label": "🔵 Google (Gemini)", "color": "🔵", "default_limit_5h": 1_500_000, "default_limit_w": 7_500_000},
        "opensource": {"name": "Açık Kaynak & Yerel", "label": "🌐 Açık Kaynak / Yerel (0 TL)", "color": "🌐", "default_limit_5h": REF_FREE_LIMIT_5H, "default_limit_w": REF_FREE_LIMIT_WEEKLY},
    }

    # 1. En Çok Token Harcayan (En Ağır Kota & En Yüksek Efor) Modellerden Aşağıya Doğru Sabit Standart Sıra
    PAID_REFERENCE_MODELS = [
        # --- 🟣 ANTHROPIC (CLAUDE OPUS, SONNET, FABLE, HAIKU) ---
        {"name": "Claude Opus 5.5 (Max)", "provider": "anthropic", "match_keys": ["claude-opus-5-5-max", "opus-5.5-max"], "tier": "premium", "is_free": False, "limit_5h": 200_000, "limit_weekly": 1_000_000, "quota_type": "💎 200K (5s) • 1.00M (Hafta)"},
        {"name": "Claude Opus 5.5 (High)", "provider": "anthropic", "match_keys": ["claude-opus-5-5-high", "opus-5.5-high"], "tier": "premium", "is_free": False, "limit_5h": 250_000, "limit_weekly": 1_250_000, "quota_type": "💎 250K (5s) • 1.25M (Hafta)"},
        {"name": "Claude Opus 5.5 (Medium)", "provider": "anthropic", "match_keys": ["claude-opus-5-5-medium", "opus-5.5-medium", "claude-opus-5.5"], "tier": "premium", "is_free": False, "limit_5h": 250_000, "limit_weekly": 1_250_000, "quota_type": "💎 250K (5s) • 1.25M (Hafta)"},
        {"name": "Claude Opus 5.5 (Low)", "provider": "anthropic", "match_keys": ["claude-opus-5-5-low", "opus-5.5-low"], "tier": "premium", "is_free": False, "limit_5h": 300_000, "limit_weekly": 1_500_000, "quota_type": "💎 300K (5s) • 1.50M (Hafta)"},
        {"name": "Claude Opus 4.8", "provider": "anthropic", "match_keys": ["claude-opus-4-8", "claude-opus-4.8", "opus-4.8"], "tier": "premium", "is_free": False, "limit_5h": 300_000, "limit_weekly": 1_500_000, "quota_type": "💎 300K (5s) • 1.50M (Hafta)"},
        {"name": "Claude Opus 4.6", "provider": "anthropic", "match_keys": ["claude-opus-4-6", "claude-opus-4.6", "opus-4.6"], "tier": "premium", "is_free": False, "limit_5h": 300_000, "limit_weekly": 1_500_000, "quota_type": "💎 300K (5s) • 1.50M (Hafta)"},
        {"name": "Claude Opus 4.5", "provider": "anthropic", "match_keys": ["claude-opus-4-5", "claude-opus-4.5", "opus-4.5", "4.5-opus"], "tier": "premium", "is_free": False, "limit_5h": 300_000, "limit_weekly": 1_500_000, "quota_type": "💎 300K (5s) • 1.50M (Hafta)"},
        {"name": "Claude Sonnet 5.5 (Max)", "provider": "anthropic", "match_keys": ["claude-sonnet-5-5-max", "sonnet-5.5-max"], "tier": "premium", "is_free": False, "limit_5h": 350_000, "limit_weekly": 1_750_000, "quota_type": "💎 350K (5s) • 1.75M (Hafta)"},
        {"name": "Claude Sonnet 5.5 (High)", "provider": "anthropic", "match_keys": ["claude-sonnet-5-5-high", "sonnet-5.5-high"], "tier": "premium", "is_free": False, "limit_5h": 400_000, "limit_weekly": 2_000_000, "quota_type": "💎 400K (5s) • 2.00M (Hafta)"},
        {"name": "Claude Fable 5.1", "provider": "anthropic", "match_keys": ["fable-5.1", "fable", "claude-fable"], "tier": "premium", "is_free": False, "limit_5h": 400_000, "limit_weekly": 2_000_000, "quota_type": "💎 400K (5s) • 2.00M (Hafta)"},
        {"name": "Claude Sonnet 4.6", "provider": "anthropic", "match_keys": ["claude-sonnet-4-6", "claude-sonnet-4.6", "sonnet-4.6", "claudecode", "claude-code"], "tier": "premium", "is_free": False, "limit_5h": 400_000, "limit_weekly": 2_000_000, "quota_type": "💎 400K (5s) • 2.00M (Hafta)"},
        {"name": "Claude Sonnet 4.5", "provider": "anthropic", "match_keys": ["claude-sonnet-4-5", "claude-sonnet-4.5", "sonnet-4.5"], "tier": "premium", "is_free": False, "limit_5h": 400_000, "limit_weekly": 2_000_000, "quota_type": "💎 400K (5s) • 2.00M (Hafta)"},
        {"name": "Claude Sonnet 4.0", "provider": "anthropic", "match_keys": ["claude-sonnet-4-0", "claude-sonnet-4.0", "sonnet-4.0"], "tier": "premium", "is_free": False, "limit_5h": 400_000, "limit_weekly": 2_000_000, "quota_type": "💎 400K (5s) • 2.00M (Hafta)"},
        {"name": "Claude 3.5 Sonnet", "provider": "anthropic", "match_keys": ["claude-3-5-sonnet", "claude-3.5-sonnet", "3.5-sonnet"], "tier": "premium", "is_free": False, "limit_5h": 400_000, "limit_weekly": 2_000_000, "quota_type": "💎 400K (5s) • 2.00M (Hafta)"},
        {"name": "Claude Sonnet 5.5 (Medium)", "provider": "anthropic", "match_keys": ["claude-sonnet-5-5-medium", "sonnet-5.5-medium", "claude-sonnet-5-5"], "tier": "premium", "is_free": False, "limit_5h": 450_000, "limit_weekly": 2_250_000, "quota_type": "💎 450K (5s) • 2.25M (Hafta)"},
        {"name": "Claude Sonnet 5.5 (Low)", "provider": "anthropic", "match_keys": ["claude-sonnet-5-5-low", "sonnet-5.5-low"], "tier": "premium", "is_free": False, "limit_5h": 500_000, "limit_weekly": 2_500_000, "quota_type": "💎 500K (5s) • 2.50M (Hafta)"},
        {"name": "Claude Haiku 4.5", "provider": "anthropic", "match_keys": ["claude-haiku-4-5", "claude-haiku-4.5", "haiku-4.5"], "tier": "low_quota", "is_free": False, "limit_5h": 1_500_000, "limit_weekly": 7_500_000, "quota_type": "⚡ 1.50M (5s) • 7.50M (Hafta)"},
        {"name": "Claude Haiku 3.5", "provider": "anthropic", "match_keys": ["claude-3-5-haiku", "claude-3.5-haiku", "haiku-3.5", "haiku"], "tier": "low_quota", "is_free": False, "limit_5h": 1_500_000, "limit_weekly": 7_500_000, "quota_type": "⚡ 1.50M (5s) • 7.50M (Hafta)"},

        # --- 🟢 OPENAI (O3, O1, GPT-5, CODEX, GPT-4O, MINI, GPT-OSS) ---
        {"name": "OpenAI o3 (High)", "provider": "openai", "match_keys": ["o3-high", "openai-o3-high"], "tier": "premium", "is_free": False, "limit_5h": 350_000, "limit_weekly": 1_750_000, "quota_type": "💎 350K (5s) • 1.75M (Hafta)"},
        {"name": "OpenAI GPT-5 (High)", "provider": "openai", "match_keys": ["gpt-5-high", "openai-gpt-5-high"], "tier": "premium", "is_free": False, "limit_5h": 400_000, "limit_weekly": 2_000_000, "quota_type": "💎 400K (5s) • 2.00M (Hafta)"},
        {"name": "OpenAI o3 (Medium)", "provider": "openai", "match_keys": ["o3-medium", "openai-o3-medium", "openai-o3"], "tier": "premium", "is_free": False, "limit_5h": 400_000, "limit_weekly": 2_000_000, "quota_type": "💎 400K (5s) • 2.00M (Hafta)"},
        {"name": "OpenAI o1", "provider": "openai", "match_keys": ["o1-pro", "o1-preview", "openai-o1"], "tier": "premium", "is_free": False, "limit_5h": 400_000, "limit_weekly": 2_000_000, "quota_type": "💎 400K (5s) • 2.00M (Hafta)"},
        {"name": "OpenAI GPT-5 (Medium)", "provider": "openai", "match_keys": ["gpt-5-medium", "openai-gpt-5-medium", "openai-gpt-5"], "tier": "premium", "is_free": False, "limit_5h": 500_000, "limit_weekly": 2_500_000, "quota_type": "💎 500K (5s) • 2.50M (Hafta)"},
        {"name": "OpenAI GPT-4.5", "provider": "openai", "match_keys": ["gpt-4.5", "openai-gpt-4.5"], "tier": "premium", "is_free": False, "limit_5h": 500_000, "limit_weekly": 2_500_000, "quota_type": "💎 500K (5s) • 2.50M (Hafta)"},
        {"name": "OpenAI o3 (Low)", "provider": "openai", "match_keys": ["o3-low", "openai-o3-low"], "tier": "premium", "is_free": False, "limit_5h": 500_000, "limit_weekly": 2_500_000, "quota_type": "💎 500K (5s) • 2.50M (Hafta)"},
        {"name": "OpenAI GPT-5 (Low)", "provider": "openai", "match_keys": ["gpt-5-low", "openai-gpt-5-low"], "tier": "premium", "is_free": False, "limit_5h": 600_000, "limit_weekly": 3_000_000, "quota_type": "💎 600K (5s) • 3.00M (Hafta)"},
        {"name": "OpenAI GPT-5.2 Codex", "provider": "openai", "match_keys": ["codex", "gpt-5.2", "openai-codex"], "tier": "low_quota", "is_free": False, "limit_5h": 800_000, "limit_weekly": 4_000_000, "quota_type": "⚡ 800K (5s) • 4.00M (Hafta)"},
        {"name": "OpenAI GPT-4o", "provider": "openai", "match_keys": ["gpt-4o", "openai-gpt4o"], "tier": "low_quota", "is_free": False, "limit_5h": 800_000, "limit_weekly": 4_000_000, "quota_type": "⚡ 800K (5s) • 4.00M (Hafta)"},
        {"name": "OpenAI o4-mini (High)", "provider": "openai", "match_keys": ["o4-mini-high"], "tier": "low_quota", "is_free": False, "limit_5h": 1_000_000, "limit_weekly": 5_000_000, "quota_type": "⚡ 1.00M (5s) • 5.00M (Hafta)"},
        {"name": "OpenAI o3-mini (High)", "provider": "openai", "match_keys": ["o3-mini-high"], "tier": "low_quota", "is_free": False, "limit_5h": 1_000_000, "limit_weekly": 5_000_000, "quota_type": "⚡ 1.00M (5s) • 5.00M (Hafta)"},
        {"name": "OpenAI GPT-OSS 120B (Medium)", "provider": "openai", "match_keys": ["gpt-oss-120b-medium", "gpt-oss-120b", "oss-120b"], "tier": "low_quota", "is_free": False, "limit_5h": 1_000_000, "limit_weekly": 5_000_000, "quota_type": "⚡ 1.00M (5s) • 5.00M (Hafta)"},
        {"name": "OpenAI o4-mini (Medium)", "provider": "openai", "match_keys": ["o4-mini-medium", "o4-mini"], "tier": "low_quota", "is_free": False, "limit_5h": 1_200_000, "limit_weekly": 6_000_000, "quota_type": "⚡ 1.20M (5s) • 6.00M (Hafta)"},
        {"name": "OpenAI o3-mini (Medium)", "provider": "openai", "match_keys": ["o3-mini-medium", "o3-mini"], "tier": "low_quota", "is_free": False, "limit_5h": 1_200_000, "limit_weekly": 6_000_000, "quota_type": "⚡ 1.20M (5s) • 6.00M (Hafta)"},
        {"name": "OpenAI o4-mini (Low)", "provider": "openai", "match_keys": ["o4-mini-low"], "tier": "low_quota", "is_free": False, "limit_5h": 1_500_000, "limit_weekly": 7_500_000, "quota_type": "⚡ 1.50M (5s) • 7.50M (Hafta)"},
        {"name": "OpenAI o3-mini (Low)", "provider": "openai", "match_keys": ["o3-mini-low"], "tier": "low_quota", "is_free": False, "limit_5h": 1_500_000, "limit_weekly": 7_500_000, "quota_type": "⚡ 1.50M (5s) • 7.50M (Hafta)"},
        {"name": "OpenAI GPT-OSS 20B", "provider": "openai", "match_keys": ["gpt-oss-20b", "oss-20b"], "tier": "low_quota", "is_free": False, "limit_5h": 1_500_000, "limit_weekly": 7_500_000, "quota_type": "⚡ 1.50M (5s) • 7.50M (Hafta)"},
        {"name": "OpenAI GPT-4o-mini", "provider": "openai", "match_keys": ["gpt-4o-mini"], "tier": "low_quota", "is_free": False, "limit_5h": 2_000_000, "limit_weekly": 10_000_000, "quota_type": "⚡ 2.00M (5s) • 10.0M (Hafta)"},

        # --- 🔵 GOOGLE (GEMINI ULTRA, PRO, ARGON, FLASH) ---
        {"name": "Gemini 3.1 Ultra", "provider": "google", "match_keys": ["gemini-3.1-ultra", "3.1-ultra"], "tier": "premium", "is_free": False, "limit_5h": 600_000, "limit_weekly": 3_000_000, "quota_type": "💎 600K (5s) • 3.00M (Hafta)"},
        {"name": "Gemini 3.1 Pro (High)", "provider": "google", "match_keys": ["gemini-3.1-pro-high", "3.1-pro-high"], "tier": "premium", "is_free": False, "limit_5h": 900_000, "limit_weekly": 4_500_000, "quota_type": "💎 900K (5s) • 4.50M (Hafta)"},
        {"name": "Gemini 3.1 Pro (Medium)", "provider": "google", "match_keys": ["gemini-3.1-pro-medium", "gemini-3.1-pro", "3.1-pro", "gemini-pro"], "tier": "premium", "is_free": False, "limit_5h": 1_000_000, "limit_weekly": 5_000_000, "quota_type": "💎 1.00M (5s) • 5.00M (Hafta)"},
        {"name": "Gemini 4 Argon (High)", "provider": "google", "match_keys": ["gemini-4-argon-high", "argon-high"], "tier": "premium", "is_free": False, "limit_5h": 1_200_000, "limit_weekly": 6_000_000, "quota_type": "💎 1.20M (5s) • 6.00M (Hafta)"},
        {"name": "Gemini 3.1 Pro (Low)", "provider": "google", "match_keys": ["gemini-3.1-pro-low", "3.1-pro-low"], "tier": "premium", "is_free": False, "limit_5h": 1_200_000, "limit_weekly": 6_000_000, "quota_type": "💎 1.20M (5s) • 6.00M (Hafta)"},
        {"name": "Gemini 2.5 Pro", "provider": "google", "match_keys": ["gemini-2.5-pro", "2.5-pro"], "tier": "premium", "is_free": False, "limit_5h": 1_200_000, "limit_weekly": 6_000_000, "quota_type": "💎 1.20M (5s) • 6.00M (Hafta)"},
        {"name": "Gemini 4 Argon (Medium)", "provider": "google", "match_keys": ["gemini-4-argon-medium", "gemini-4-argon-trial", "gemini-4-argon", "argon"], "tier": "premium", "is_free": False, "limit_5h": 1_500_000, "limit_weekly": 7_500_000, "quota_type": "💎 1.50M (5s) • 7.50M (Hafta)"},
        {"name": "Gemini 4 Argon (Low)", "provider": "google", "match_keys": ["gemini-4-argon-low", "argon-low"], "tier": "premium", "is_free": False, "limit_5h": 1_800_000, "limit_weekly": 9_000_000, "quota_type": "💎 1.80M (5s) • 9.00M (Hafta)"},
        {"name": "Gemini 3.8 Flash (High)", "provider": "google", "match_keys": ["gemini-3.8-flash-high", "3.8-flash-high"], "tier": "low_quota", "is_free": False, "limit_5h": 2_000_000, "limit_weekly": 10_000_000, "quota_type": "⚡ 2.00M (5s) • 10.0M (Hafta)"},
        {"name": "Gemini 3.7 Flash (High)", "provider": "google", "match_keys": ["gemini-3.7-flash-high", "3.7-flash-high"], "tier": "low_quota", "is_free": False, "limit_5h": 2_000_000, "limit_weekly": 10_000_000, "quota_type": "⚡ 2.00M (5s) • 10.0M (Hafta)"},
        {"name": "Gemini 3.8 Flash (Medium)", "provider": "google", "match_keys": ["gemini-3.8-flash-medium", "gemini-3.8-flash-tiered", "gemini-3.8-flash", "3.8-flash", "flash"], "tier": "low_quota", "is_free": False, "limit_5h": 2_500_000, "limit_weekly": 12_500_000, "quota_type": "⚡ 2.50M (5s) • 12.5M (Hafta)"},
        {"name": "Gemini 3.7 Flash (Medium)", "provider": "google", "match_keys": ["gemini-3.7-flash-medium", "gemini-3.7-flash"], "tier": "low_quota", "is_free": False, "limit_5h": 2_500_000, "limit_weekly": 12_500_000, "quota_type": "⚡ 2.50M (5s) • 12.5M (Hafta)"},
        {"name": "Gemini 3.6 Flash (Medium)", "provider": "google", "match_keys": ["gemini-3.6-flash-medium", "gemini-3.6-flash"], "tier": "low_quota", "is_free": False, "limit_5h": 2_500_000, "limit_weekly": 12_500_000, "quota_type": "⚡ 2.50M (5s) • 12.5M (Hafta)"},
        {"name": "Gemini 3.5 Flash (High)", "provider": "google", "match_keys": ["gemini-3.5-flash-high", "3.5-flash-high"], "tier": "low_quota", "is_free": False, "limit_5h": 2_500_000, "limit_weekly": 12_500_000, "quota_type": "⚡ 2.50M (5s) • 12.5M (Hafta)"},
        {"name": "Gemini 2.5 Flash", "provider": "google", "match_keys": ["gemini-2.5-flash", "2.5-flash"], "tier": "low_quota", "is_free": False, "limit_5h": 2_500_000, "limit_weekly": 12_500_000, "quota_type": "⚡ 2.50M (5s) • 12.5M (Hafta)"},
        {"name": "Gemini 3.8 Flash (Low)", "provider": "google", "match_keys": ["gemini-3.8-flash-low", "3.8-flash-low"], "tier": "low_quota", "is_free": False, "limit_5h": 3_000_000, "limit_weekly": 15_000_000, "quota_type": "⚡ 3.00M (5s) • 15.0M (Hafta)"},
        {"name": "Gemini 3.7 Flash (Low)", "provider": "google", "match_keys": ["gemini-3.7-flash-low", "3.7-flash-low"], "tier": "low_quota", "is_free": False, "limit_5h": 3_000_000, "limit_weekly": 15_000_000, "quota_type": "⚡ 3.00M (5s) • 15.0M (Hafta)"},
        {"name": "Gemini 3.6 Flash (Low)", "provider": "google", "match_keys": ["gemini-3.6-flash-low", "3.6-flash-low"], "tier": "low_quota", "is_free": False, "limit_5h": 3_000_000, "limit_weekly": 15_000_000, "quota_type": "⚡ 3.00M (5s) • 15.0M (Hafta)"},
        {"name": "Gemini 3.5 Flash (Low)", "provider": "google", "match_keys": ["gemini-3.5-flash-low", "gemini-3.5-flash"], "tier": "low_quota", "is_free": False, "limit_5h": 3_000_000, "limit_weekly": 15_000_000, "quota_type": "⚡ 3.00M (5s) • 15.0M (Hafta)"},
    ]

    # 2. Ücretsiz & Yerel (0 TL) Modeller (🌐 Açık Kaynak, Yerel GPU & Ücretsiz Sağlayıcılar)
    FREE_REFERENCE_MODELS = [
        {"name": "Gemini 3.5 Flash-Lite", "provider": "google", "match_keys": ["3.5-flash-lite", "flash_lite", "flash-lite"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (Hafif İşçi)"},
        {"name": "Gemini 3.1 Flash-Lite", "provider": "google", "match_keys": ["3.1-flash-lite"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (Hafif İşçi)"},
        {"name": "OpenCode Big-Pickle", "provider": "opensource", "match_keys": ["opencode", "big-pickle"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (OpenCode)"},
        {"name": "Hermes 3 Nous 405B", "provider": "opensource", "match_keys": ["hermes", "nous-405b", "nous"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (Hermes)"},
        {"name": "Hermes 3 Nous 70B", "provider": "opensource", "match_keys": ["nous-70b", "hermes-70b"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (Hermes)"},
        {"name": "Llama 3 8B (Yerel RTX 5070 Ti)", "provider": "opensource", "match_keys": ["llama3", "llama-3", "yerelollama", "ollama"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (Yerel GPU)"},
        {"name": "Qwen 2.5 Coder 14B (Yerel RTX 5070 Ti)", "provider": "opensource", "match_keys": ["qwen-14b", "qwen2.5-coder:14b", "qwen-coder"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (Yerel GPU)"},
        {"name": "DeepSeek R1 14B (Yerel RTX 5070 Ti)", "provider": "opensource", "match_keys": ["deepseek-r1:14b", "deepseek-local"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (Yerel GPU)"},
        {"name": "NVIDIA Llama 3.1 Nemotron 70B:free", "provider": "opensource", "match_keys": ["nvidia", "nemotron", "nim"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (NVIDIA NIM)"},
        {"name": "NVIDIA DeepSeek R1:free", "provider": "opensource", "match_keys": ["nvidia-deepseek", "nim-deepseek"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (NVIDIA NIM)"},
        {"name": "HuggingFace Qwen 2.5 Coder 32B:free", "provider": "opensource", "match_keys": ["huggingface", "hf-qwen", "hf"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (HuggingFace)"},
        {"name": "HuggingFace Zephyr 7B Beta:free", "provider": "opensource", "match_keys": ["zephyr", "hf-zephyr"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (HuggingFace)"},
        {"name": "OpenRouter Qwen 2.5 Coder 32B:free", "provider": "opensource", "match_keys": ["openrouterfree", "openrouter", ":free"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (OpenRouter Free)"},
        {"name": "OpenRouter DeepSeek V3:free", "provider": "opensource", "match_keys": ["deepseek-v3:free", "openrouter-deepseek"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL (OpenRouter Free)"},
    ]

    def __init__(
        self,
        storage_path: str = "config/usage_events.json",
        brain_dir: str = r"C:\Users\kloss\.gemini\antigravity-cli\brain",
    ):
        self.storage_path = str(storage_path)
        self.brain_dir = str(brain_dir)

    def _load_events(self) -> List[Dict[str, Any]]:
        """Kayıtlı olayları JSON dosyasından güvenle yükler."""
        if not os.path.exists(self.storage_path):
            return []
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_events(self, events: List[Dict[str, Any]]) -> None:
        """Olayları JSON dosyasına kaydeder."""
        dirname = os.path.dirname(self.storage_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def record_event(
        self,
        category: str,
        name: str,
        tier: str = "free",
        is_free: bool = True,
        tokens_est: int = 0,
        source: str = "workstation",
        timestamp: str | None = None,
    ) -> Dict[str, Any]:
        """Yeni bir kullanım olayını kaydeder."""
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        if tokens_est <= 0:
            tokens_est = 6500 if category == "agent" else (5000 if category == "model" else 4000)

        event = {
            "category": str(category),
            "name": str(name),
            "tier": str(tier),
            "is_free": bool(is_free),
            "tokens_est": int(tokens_est),
            "source": str(source),
            "timestamp": str(timestamp),
        }

        events = self._load_events()
        events.append(event)
        self._save_events(events)
        return event

    def classify_model_or_tool(self, name: str) -> Dict[str, Any]:
        """Model veya CLI adına göre sınıflandırma yapar."""
        n = (name or "").strip()
        n_lower = n.lower()

        if any(k in n_lower for k in ["flash_lite", "flash-lite", "tier_flash_lite", "3.5-flash-lite"]):
            return {
                "is_free": True,
                "tier": "free",
                "cli_name": "flash_lite",
                "display_name": "Gemini 3.5 Flash-Lite (0 TL / Hafif İşçi)",
            }

        free_keywords = [
            "yerelollama",
            "ollama",
            "llama",
            "qwen",
            "deepseek",
            "openrouterfree",
            ":free",
            "openrouter/free",
            "hermes",
            "opencode",
            "unittest",
            "pytest",
            "nvidia",
            "nemotron",
            "nim",
            "huggingface",
            "hf",
            "zephyr",
        ]
        if any(k in n_lower for k in free_keywords):
            cli_name = "ollama"
            if "hermes" in n_lower:
                cli_name = "hermes"
            elif "opencode" in n_lower:
                cli_name = "opencode"
            elif "nvidia" in n_lower or "nemotron" in n_lower or "nim" in n_lower:
                cli_name = "nvidia_nim"
            elif "huggingface" in n_lower or "hf" in n_lower or "zephyr" in n_lower:
                cli_name = "huggingface"
            elif ":free" in n_lower or "openrouter" in n_lower:
                cli_name = "openrouter"
            elif "unittest" in n_lower or "pytest" in n_lower:
                cli_name = "test_runner"

            return {
                "is_free": True,
                "tier": "free",
                "cli_name": cli_name,
                "display_name": f"{n} (Ücretsiz / 0 TL)",
            }

        low_quota_keywords = ["flash", "tier_flash", "codex", "3.8-flash", "gpt-oss"]
        if any(k in n_lower for k in low_quota_keywords):
            cli_name = "gemini_flash"
            if "codex" in n_lower:
                cli_name = "codex"
            return {
                "is_free": False,
                "tier": "low_quota",
                "cli_name": cli_name,
                "display_name": f"{n} (Düşük Kota İşçisi)",
            }

        premium_keywords = ["claudecode", "claude", "pro", "tier_pro", "gemini-pro", "argon", "opus", "fable", "sonnet"]
        if any(k in n_lower for k in premium_keywords):
            cli_name = "claude" if "claude" in n_lower else "gemini_pro"
            return {
                "is_free": False,
                "tier": "premium",
                "cli_name": cli_name,
                "display_name": f"{n} (Uzman Katman)",
            }

        if "free" in n_lower:
            return {
                "is_free": True,
                "tier": "free",
                "cli_name": n_lower,
                "display_name": f"{n} (0 TL)",
            }

        return {
            "is_free": True,
            "tier": "free",
            "cli_name": n_lower,
            "display_name": f"{n} (Yerel)",
        }

    def scan_antigravity_brain(self) -> List[Dict[str, Any]]:
        """Antigravity transcript dosyalarını tarar."""
        brain_path = Path(self.brain_dir)
        events: List[Dict[str, Any]] = []

        if not brain_path.exists():
            return events

        target_files: List[Path] = []
        try:
            conv_dirs = [d for d in brain_path.iterdir() if d.is_dir()]
            for cdir in conv_dirs:
                logs_dir = cdir / ".system_generated" / "logs"
                t_full = logs_dir / "transcript_full.jsonl"
                t_norm = logs_dir / "transcript.jsonl"
                if t_full.exists():
                    target_files.append(t_full)
                elif t_norm.exists():
                    target_files.append(t_norm)
        except Exception:
            pass

        if not target_files:
            full_list = list(brain_path.rglob("transcript_full.jsonl"))
            if full_list:
                target_files = full_list
            else:
                target_files = list(brain_path.rglob("transcript.jsonl"))

        cli_patterns = [
            (r"\bclaude\b", "ClaudeCode"),
            (r"\bcodex\b", "Codex"),
            (r"\bhermes\b", "Hermes"),
            (r"\bopencode\b", "OpenCode"),
            (r"\bollama\b", "YerelOllama"),
            (r"\b(unittest|pytest)\b", "TestRunner"),
        ]

        for t_file in target_files:
            try:
                with open(t_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        try:
                            item = json.loads(line_str)
                        except Exception:
                            continue

                        ts = item.get("created_at")
                        tool_calls = item.get("tool_calls", [])
                        if not tool_calls or not isinstance(tool_calls, list):
                            continue

                        raw_in = item.get("input_tokens", 0) or 0
                        raw_out = item.get("output_tokens", 0) or 0
                        base_tokens = max(raw_in + raw_out, len(line_str) // 3)
                        if base_tokens < 5000:
                            base_tokens = 15000

                        for call in tool_calls:
                            if not isinstance(call, dict):
                                continue
                            tool_name = call.get("name")
                            args = call.get("args", {})
                            if not isinstance(args, dict):
                                continue

                            # 1. Alt ajan başlatma (invoke_subagent)
                            if tool_name == "invoke_subagent":
                                subagents_data = (
                                    args.get("Subagents")
                                    or args.get("subagents")
                                    or args.get("agents")
                                )
                                if isinstance(subagents_data, str):
                                    try:
                                        subagents_data = json.loads(subagents_data)
                                    except Exception:
                                        subagents_data = []

                                if isinstance(subagents_data, dict):
                                    subagents_data = [subagents_data]
                                elif not isinstance(subagents_data, list):
                                    subagents_data = []

                                for sub in subagents_data:
                                    if not isinstance(sub, dict):
                                        continue
                                    model = (
                                        sub.get("Model")
                                        or sub.get("model")
                                        or sub.get("modelTier")
                                        or "flash"
                                    )
                                    role = (
                                        sub.get("Role")
                                        or sub.get("role")
                                        or sub.get("name")
                                        or "Nexus Worker"
                                    )
                                    cls_info = self.classify_model_or_tool(model)
                                    sub_tokens = max(base_tokens, len(sub.get("Prompt", "")) // 3 + 10000)

                                    events.append({
                                        "category": "agent",
                                        "name": role,
                                        "model_used": str(model),
                                        "tier": cls_info["tier"],
                                        "is_free": cls_info["is_free"],
                                        "tokens_est": sub_tokens,
                                        "source": "antigravity",
                                        "timestamp": ts,
                                    })

                            # 2. Alt ajana ek görev mesajı gönderme (send_message)
                            elif tool_name == "send_message":
                                recipient = str(args.get("Recipient", ""))
                                msg = str(args.get("Message", ""))
                                summary = str(args.get("toolSummary") or "Alt Ajan Görevi")
                                short_id = recipient[:8] if recipient else "worker"
                                msg_tokens = max(len(msg) // 3 + 3000, 6000)

                                events.append({
                                    "category": "agent",
                                    "name": f"Ek Görev ({summary} - {short_id})",
                                    "model_used": "gemini-3.8-flash-medium",
                                    "tier": "low_quota",
                                    "is_free": False,
                                    "tokens_est": msg_tokens,
                                    "source": "antigravity",
                                    "timestamp": ts,
                                })

                            # 3. CLI çalıştırma (run_command)
                            elif tool_name == "run_command":
                                cmd = str(args.get("CommandLine", ""))
                                cmd_lower = cmd.lower()
                                detected_clis = set()
                                for pattern, cli_key in cli_patterns:
                                    if re.search(pattern, cmd_lower):
                                        detected_clis.add(cli_key)

                                cli_tokens = max(len(cmd) // 3 + 5000, 8000)
                                for cli_key in detected_clis:
                                    cls_info = self.classify_model_or_tool(cli_key)
                                    events.append({
                                        "category": "cli",
                                        "name": cli_key,
                                        "tier": cls_info["tier"],
                                        "is_free": cls_info["is_free"],
                                        "tokens_est": cli_tokens,
                                        "source": "antigravity",
                                        "timestamp": ts,
                                    })
            except Exception:
                continue

        return events

    def scan_conversations_db(self) -> List[Dict[str, Any]]:
        r"""
        C:\Users\kloss\.gemini\antigravity-cli\conversations\*.db SQLite veritabanlarını tarar.
        gen_metadata tablosundan gerçek alt model adlarını (gemini-4-argon, gemini-3.8-flash, vb.) çıkarır.
        """
        events: List[Dict[str, Any]] = []
        conv_dir = Path(self.brain_dir).parent / "conversations"
        if not conv_dir.exists():
            return events

        db_files = list(conv_dir.glob("*.db"))

        for db_file in db_files:
            try:
                mtime_dt = datetime.fromtimestamp(os.path.getmtime(db_file), tz=timezone.utc)
                mtime_iso = mtime_dt.isoformat()

                conn = sqlite3.connect(str(db_file), timeout=2.0)
                cur = conn.cursor()
                cur.execute("SELECT idx, data FROM gen_metadata")
                rows = cur.fetchall()
                conn.close()

                for row in rows:
                    data = row[1]
                    if not isinstance(data, (bytes, bytearray)):
                        continue

                    model_found = None
                    matches = re.findall(rb"gemini-[a-zA-Z0-9_.-]+", data)
                    if matches:
                        model_found = matches[0].decode("ascii", "ignore")
                    elif b"\x9a\x01" in data:
                        idx = data.find(b"\x9a\x01")
                        try:
                            length = data[idx + 2]
                            raw_name = data[idx + 3 : idx + 3 + length].decode("utf-8", "ignore")
                            if raw_name.startswith("gemini-"):
                                model_found = raw_name
                        except Exception:
                            pass

                    if model_found:
                        cls_info = self.classify_model_or_tool(model_found)
                        tok_est = 1100  # Önbellek sonrası net adım maliyeti
                        events.append({
                            "category": "model",
                            "name": model_found,
                            "tier": cls_info["tier"],
                            "is_free": cls_info["is_free"],
                            "tokens_est": tok_est,
                            "source": "antigravity_db",
                            "timestamp": mtime_iso,
                        })
            except Exception:
                continue

        return events

    @staticmethod
    def _parse_timestamp(ts: Optional[str]) -> Optional[datetime]:
        """ISO tarih stringini datetime objesine dönüştürür."""
        if not ts:
            return None
        try:
            ts_clean = str(ts).replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def get_report(self, include_antigravity: bool = True) -> Dict[str, Any]:
        """five_hours (Son 5 Saat), daily, weekly ve monthly pencerelerini üretir."""
        all_events = list(self._load_events())
        if include_antigravity:
            antigravity_events = self.scan_antigravity_brain()
            all_events.extend(antigravity_events)
            # conversations/*.db SQLite veritabanını da tara
            db_events = self.scan_conversations_db()
            all_events.extend(db_events)

        now = datetime.now(timezone.utc)

        window_seconds = {
            "five_hours": 5 * 3600,
            "daily": 24 * 3600,
            "weekly": 7 * 24 * 3600,
            "monthly": 30 * 24 * 3600,
        }

        report: Dict[str, Any] = {
            "generated_at": now.isoformat(),
            "five_hours": {},
            "daily": {},
            "weekly": {},
            "monthly": {},
        }

        for window_key, max_sec in window_seconds.items():
            filtered_events: List[Dict[str, Any]] = []
            for ev in all_events:
                dt = self._parse_timestamp(ev.get("timestamp"))
                if not dt:
                    continue
                diff_sec = (now - dt).total_seconds()
                if -120 <= diff_sec <= max_sec:
                    filtered_events.append(ev)

            total = len(filtered_events)
            free_cnt = sum(
                1 for e in filtered_events if e.get("is_free") or e.get("tier") == "free"
            )
            low_quota_cnt = sum(
                1 for e in filtered_events if e.get("tier") == "low_quota"
            )
            premium_cnt = sum(
                1 for e in filtered_events if e.get("tier") == "premium"
            )

            tokens_total = sum(e.get("tokens_est", 0) for e in filtered_events)
            tokens_free = sum(e.get("tokens_est", 0) for e in filtered_events if e.get("is_free") or e.get("tier") == "free")
            tokens_low = sum(e.get("tokens_est", 0) for e in filtered_events if e.get("tier") == "low_quota")
            tokens_prem = sum(e.get("tokens_est", 0) for e in filtered_events if e.get("tier") == "premium")

            ratio = (
                round(((free_cnt + low_quota_cnt) / total * 100), 2)
                if total > 0
                else 0.0
            )
            saved_usd = round((free_cnt * 0.03) + (low_quota_cnt * 0.02), 2)

            # Modeller listesi
            model_counts: Dict[str, Dict[str, Any]] = {}
            for e in filtered_events:
                if e.get("category") == "model":
                    name = e.get("name", "Bilinmeyen")
                    if name not in model_counts:
                        model_counts[name] = {
                            "name": name,
                            "count": 0,
                            "tokens": 0,
                            "tier": e.get("tier", "free"),
                            "is_free": e.get("is_free", True),
                        }
                    model_counts[name]["count"] += 1
                    model_counts[name]["tokens"] += e.get("tokens_est", 0)
            models_list = sorted(
                model_counts.values(), key=lambda x: x["count"], reverse=True
            )

            # CLI'lar listesi
            cli_counts: Dict[str, Dict[str, Any]] = {}
            for e in filtered_events:
                if e.get("category") == "cli":
                    name = e.get("name", "Bilinmeyen")
                    if name not in cli_counts:
                        cli_counts[name] = {
                            "name": name,
                            "count": 0,
                            "tokens": 0,
                            "tier": e.get("tier", "free"),
                            "is_free": e.get("is_free", True),
                        }
                    cli_counts[name]["count"] += 1
                    cli_counts[name]["tokens"] += e.get("tokens_est", 0)
            clis_list = sorted(
                cli_counts.values(), key=lambda x: x["count"], reverse=True
            )

            # Ajanlar listesi
            agent_counts: Dict[str, Dict[str, Any]] = {}
            for e in filtered_events:
                if e.get("category") == "agent":
                    name = e.get("name", "Worker")
                    source = e.get("source", "workstation")
                    key = f"{name}_{source}"
                    if key not in agent_counts:
                        agent_counts[key] = {
                            "name": name,
                            "count": 0,
                            "tokens": 0,
                            "tier": e.get("tier", "free"),
                            "source": source,
                        }
                    agent_counts[key]["count"] += 1
                    agent_counts[key]["tokens"] += e.get("tokens_est", 0)
            agents_list = sorted(
                agent_counts.values(), key=lambda x: x["count"], reverse=True
            )

            free_usages = {
                "total_free": free_cnt,
                "low_quota": low_quota_cnt,
                "tokens_free": tokens_free,
                "tokens_low": tokens_low,
                "estimated_saved_usd": saved_usd,
                "free_and_worker_ratio": ratio,
                "models": [m for m in models_list if m.get("is_free")],
                "clis": [c for c in clis_list if c.get("is_free")],
            }

            report[window_key] = {
                "total_events": total,
                "free_events": free_cnt,
                "low_quota_events": low_quota_cnt,
                "premium_events": premium_cnt,
                "tokens_total": tokens_total,
                "tokens_free": tokens_free,
                "tokens_low_quota": tokens_low,
                "tokens_premium": tokens_prem,
                "free_And_worker_ratio": ratio,
                "free_and_worker_ratio": ratio,
                "estimated_saved_usd": saved_usd,
                "models": models_list,
                "clis": clis_list,
                "agents": agents_list,
                "free_usages": free_usages,
                "_raw_events": filtered_events,
            }

        report["all_time_totals"] = {
            "total_events": len(all_events),
            "free_events": sum(
                1 for e in all_events if e.get("is_free") or e.get("tier") == "free"
            ),
            "low_quota_events": sum(
                1 for e in all_events if e.get("tier") == "low_quota"
            ),
            "premium_events": sum(
                1 for e in all_events if e.get("tier") == "premium"
            ),
            "tokens_total": sum(e.get("tokens_est", 0) for e in all_events),
        }

        return report

    def _aggregate_model_tokens(self, raw_events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Hem model, hem CLI hem de conversations/*.db SQLite olaylarını model bazında birleştirir."""
        all_specs = self.PAID_REFERENCE_MODELS + self.FREE_REFERENCE_MODELS
        data = {
            spec["name"]: {
                "count": 0,
                "tokens": 0,
                "tier": spec["tier"],
                "provider": spec.get("provider", "opensource"),
                "is_free": spec["is_free"],
                "limit_5h": spec.get("limit_5h", REF_FREE_LIMIT_5H),
                "limit_weekly": spec.get("limit_weekly", REF_FREE_LIMIT_WEEKLY),
                "quota_type": spec.get("quota_type", ""),
            }
            for spec in all_specs
        }

        for ev in raw_events:
            cat = ev.get("category")
            name = (ev.get("name") or "").lower()
            tok = ev.get("tokens_est", 0) or 5000

            # Özel eşleştirme kuralları (Önce Flash-Lite ki 'flash' ile karışmasın)
            matched = False
            if "3.1-flash-lite" in name:
                data["Gemini 3.1 Flash-Lite"]["count"] += 1
                data["Gemini 3.1 Flash-Lite"]["tokens"] += tok
                continue
            elif "lite" in name:
                data["Gemini 3.5 Flash-Lite"]["count"] += 1
                data["Gemini 3.5 Flash-Lite"]["tokens"] += tok
                continue

            # Tüm tanımlı alt modeller üzerinden sırayla eşleştir
            for spec in all_specs:
                if any(k in name for k in spec["match_keys"]):
                    data[spec["name"]]["count"] += 1
                    data[spec["name"]]["tokens"] += tok
                    matched = True
                    break

            if not matched and cat == "model":
                raw_name = ev.get("name", "Diğer")
                if raw_name not in data:
                    data[raw_name] = {
                        "count": 0,
                        "tokens": 0,
                        "tier": "free",
                        "provider": "opensource",
                        "is_free": True,
                        "limit_5h": REF_FREE_LIMIT_5H,
                        "limit_weekly": REF_FREE_LIMIT_WEEKLY,
                        "quota_type": "🟢 0 TL",
                    }
                data[raw_name]["count"] += 1
                data[raw_name]["tokens"] += tok

        return data

    def _aggregate_provider_tokens(self, m_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Modellerin toplam tokenlarını sağlayıcı / firma (Google, Anthropic, OpenAI, Açık Kaynak) bazında toplar."""
        res = {
            p_key: {
                "tokens": 0,
                "count": 0,
                "limit_5h": p_info["default_limit_5h"],
                "limit_w": p_info["default_limit_w"],
                "name": p_info["name"],
                "label": p_info["label"],
                "color": p_info["color"],
                "is_free": (p_key == "opensource"),
            }
            for p_key, p_info in self.PROVIDERS.items()
        }
        all_specs = self.PAID_REFERENCE_MODELS + self.FREE_REFERENCE_MODELS
        spec_map = {s["name"]: s for s in all_specs}

        for m_name, info in m_data.items():
            tok = info.get("tokens", 0)
            cnt = info.get("count", 0)
            if tok <= 0:
                continue
            spec = spec_map.get(m_name, {})
            p_key = spec.get("provider", "opensource")
            if p_key not in res:
                p_key = "opensource"
            res[p_key]["tokens"] += tok
            res[p_key]["count"] += cnt

        return res

    def _resolve_model_spec(self, raw_model: str) -> Dict[str, Any]:
        """Verilen ham model/araç adını referans model tanımına (spec) eşler."""
        m_low = (raw_model or "").lower()
        all_specs = self.PAID_REFERENCE_MODELS + self.FREE_REFERENCE_MODELS

        if "3.1-flash-lite" in m_low:
            for s in self.FREE_REFERENCE_MODELS:
                if s["name"] == "Gemini 3.1 Flash-Lite":
                    return s
        elif "lite" in m_low:
            for s in self.FREE_REFERENCE_MODELS:
                if s["name"] == "Gemini 3.5 Flash-Lite":
                    return s

        for s in all_specs:
            if any(k in m_low for k in s["match_keys"]):
                return s

        prov = "google" if "gemini" in m_low or "argon" in m_low else ("anthropic" if "claude" in m_low or "sonnet" in m_low or "opus" in m_low or "haiku" in m_low else ("openai" if "gpt" in m_low or "o3" in m_low or "o1" in m_low or "codex" in m_low else "opensource"))

        return {
            "name": raw_model or "Gemini 3.8 Flash (Medium)",
            "provider": prov,
            "tier": "free",
            "is_free": True,
            "limit_5h": REF_FREE_LIMIT_5H,
            "limit_weekly": REF_FREE_LIMIT_WEEKLY,
            "quota_type": "🟢 0 TL",
        }

    def _aggregate_agent_tokens(self, raw_events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Ajan olaylarını (Ajan Rolü, Kullandığı Model & Efor) bazında tek tek toplar."""
        data: Dict[str, Dict[str, Any]] = {}

        def _add_agent_entry(agent_label: str, model_spec: Dict[str, Any], tok_val: int):
            m_name = model_spec["name"]
            key = f"{agent_label}|||{m_name}"
            if key not in data:
                data[key] = {
                    "agent_name": agent_label,
                    "model_name": m_name,
                    "provider": model_spec.get("provider", "opensource"),
                    "tier": model_spec["tier"],
                    "is_free": model_spec["is_free"],
                    "limit_5h": model_spec.get("limit_5h", REF_FREE_LIMIT_5H),
                    "limit_weekly": model_spec.get("limit_weekly", REF_FREE_LIMIT_WEEKLY),
                    "count": 0,
                    "tokens": 0,
                }
            data[key]["count"] += 1
            data[key]["tokens"] += tok_val

        cli_agent_map = {
            "claudecode": ("💎 Claude Code Uzman Ajanı", "claude-sonnet-4.6"),
            "codex": ("⚡ OpenAI Codex İşçi Ajanı", "gpt-5.2"),
            "opencode": ("🟢 OpenCode CLI Ajanı", "opencode"),
            "hermes": ("🟢 Hermes CLI Ajanı", "hermes"),
            "yerelollama": ("🟢 Yerel Ollama GPU Ajanı", "llama3"),
        }

        for ev in raw_events:
            cat = ev.get("category")
            src = ev.get("source", "")
            tok = ev.get("tokens_est", 0) or 8000

            if cat == "agent":
                raw_name = ev.get("name", "")
                norm_name = normalize_agent_name(raw_name)
                raw_model = ev.get("model_used") or ""
                if not raw_model:
                    if "lite" in raw_name.lower() or ev.get("tier") == "free":
                        raw_model = "nvidia" if "terminal" in norm_name.lower() else "gemini-3.5-flash-lite"
                    elif ev.get("tier") == "premium":
                        raw_model = "gemini-4-argon-medium"
                    else:
                        raw_model = "gemini-3.8-flash-medium"
                spec = self._resolve_model_spec(raw_model)
                _add_agent_entry(norm_name, spec, tok)

            elif src == "antigravity_db" and "argon" in (ev.get("name") or "").lower():
                spec = self._resolve_model_spec(ev.get("name", "gemini-4-argon-medium"))
                _add_agent_entry("🧠 Antigravity Yönetici Beyin (Ana Orkestratör)", spec, tok)

            elif cat == "cli":
                c_key = (ev.get("name") or "").lower()
                if c_key in cli_agent_map:
                    ag_label, m_hint = cli_agent_map[c_key]
                    spec = self._resolve_model_spec(m_hint)
                    _add_agent_entry(ag_label, spec, tok)

        return data

    def _aggregate_cli_tokens(self, raw_events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """CLI olaylarını toplar ve Antigravity ile 4KWorkstation CLI kullanımlarını da hesaplar."""
        data: Dict[str, Dict[str, Any]] = {}
        for ev in raw_events:
            cat = ev.get("category")
            src = ev.get("source", "")
            tok = ev.get("tokens_est", 0) or 7000

            if cat == "cli":
                name = ev.get("name", "")
                if name not in data:
                    data[name] = {"count": 0, "tokens": 0}
                data[name]["count"] += 1
                data[name]["tokens"] += tok
            if src == "antigravity_db":
                if "Antigravity" not in data:
                    data["Antigravity"] = {"count": 0, "tokens": 0}
                data["Antigravity"]["count"] += 1
                data["Antigravity"]["tokens"] += tok
            if src == "workstation":
                if "4KWorkstation" not in data:
                    data["4KWorkstation"] = {"count": 0, "tokens": 0}
                data["4KWorkstation"]["count"] += 1
                data["4KWorkstation"]["tokens"] += tok
        return data

    def audit_paid_api_risks(self, providers_path: str = "config/providers.json") -> Dict[str, Any]:
        """
        Sistemde ücretli API riski olup olmadığını denetler.
        1. Ortam değişkenlerinde (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, CLAUDE_API_KEY)
           gerçek bir anahtar var mı bakar.
        2. config/providers.json içinde yerel olmayan (127.0.0.1/localhost dışı) ve model adında ':free'
           bulunmayan veya cost > 0 olan herhangi bir sağlayıcı eklenmiş mi kontrol eder.
        """
        warnings = []

        # 1. Ortam değişkenleri denetimi
        paid_env_keys = [
            ("OPENAI_API_KEY", "OpenAI"),
            ("ANTHROPIC_API_KEY", "Anthropic"),
            ("GEMINI_API_KEY", "Google Gemini"),
            ("CLAUDE_API_KEY", "Claude"),
        ]
        for env_key, provider_label in paid_env_keys:
            val = os.environ.get(env_key, "").strip()
            if val and not val.startswith("dummy") and not val.startswith("mock") and not val.startswith("test"):
                warnings.append(
                    f"🚨 UYARI: '{env_key}' ({provider_label}) ücretli API anahtarı ortamda tespit edildi ve otomatik olarak engellendi! Kaldırmak için ortam değişkenini silin."
                )

        # 2. config/providers.json denetimi
        if os.path.exists(providers_path):
            try:
                with open(providers_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    providers = data.get("providers", [])
                    for p in providers:
                        p_name = p.get("name", "Bilinmeyen")
                        p_model = p.get("model", "")
                        p_url = p.get("base_url", "")
                        p_cost = float(p.get("cost", 0.0) or 0.0)
                        p_local = bool(p.get("local", False))

                        is_local = p_local or ("127.0.0.1" in p_url) or ("localhost" in p_url)
                        is_explicit_free = (":free" in p_model.lower()) or ("free" in p_name.lower())

                        if not is_local:
                            if p_cost > 0.0 or not is_explicit_free:
                                warnings.append(
                                    f"🚨 UYARI: '{p_name}' ({p_model}) ücretli API tespit edildi ve otomatik olarak engellendi! Kaldırmak için '4k remove-api {p_name}' çalıştırın."
                                )
            except Exception:
                pass

        if warnings:
            return {
                "safe": False,
                "warnings": warnings,
                "status_line": "🚨 **ÜCRETLİ API TEHLİKESİ TESPİT EDİLDİ (ENGELLENDİ):** " + " | ".join(warnings),
            }

        return {
            "safe": True,
            "warnings": [],
            "status_line": "🔒 **SIFIR API HARCAMA KALKANI AKTİF ($0.00):** Sistemde hiçbir ücretli API anahtarı veya kontörlü bağlantı yok. Ücretli API eklenmeye çalışılırsa anında engellenir ve burada kırmızı uyarı verir.",
        }

    def format_all_in_one_markdown(self, include_antigravity: bool = True) -> str:
        """
        Kullanıcı '/usage' dediğinde TEK SEFERDE:
        - Sağlayıcı / Firma bazlı gruplanmış (Anthropic, OpenAI, Google, Açık Kaynak / Yerel)
        - Ücretli modelleri kendi firması içinde en ağır kotadan aşağıya doğru sıralı
        - Ücretsiz modelleri en çok kullanılandan aşağıya doğru dinamik sıralı (%100'ü geçebilen 🔥)
        - Göz karmaşasından arındırılmış, 3 sütunlu net ve görsel grafik panosu üretir.
        """
        report = self.get_report(include_antigravity=include_antigravity)
        audit = self.audit_paid_api_risks()

        h5 = report.get("five_hours", {})
        if not h5.get("total_events"):
            h5 = report.get("daily", {})
        w = report.get("weekly", {})

        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        md: List[str] = []
        md.append("# 📊 /usage — 4K AI WORKSTATION & ANTIGRAVITY KULLANIM GRAFİĞİ")
        md.append("**⏱️ 5 Saatlik & 📅 Haftalık Pencere (Model Model Ayrıntılı Kota & Token Doluluk Panosu)**")
        md.append(f"**🕒 Güncelleme:** `{now_str}` | **📁 Depolama:** `{self.storage_path}` | **🧠 Antigravity:** `{self.brain_dir}`")
        md.append("")
        if not audit["safe"]:
            md.append("> 🚨 **DİKKAT — ÜCRETLİ API TEHLİKESİ TESPİT EDİLDİ (OTOMATİK ENGELLENDİ):**")
            for w_msg in audit["warnings"]:
                md.append(f"> - {w_msg}")
        else:
            md.append(f"> {audit['status_line']}")
        md.append("")
        md.append("---")
        md.append("")

        # 1. BÖLÜM: KATMAN & FİRMA ÖZETİ
        tok_free_5h = h5.get("tokens_free", 0)
        tok_low_5h = h5.get("tokens_low_quota", 0)
        tok_prem_5h = h5.get("tokens_premium", 0)

        tok_free_w = w.get("tokens_free", 0)
        tok_low_w = w.get("tokens_low_quota", 0)
        tok_prem_w = w.get("tokens_premium", 0)

        bar_free_5h = render_model_quota_bar(tok_free_5h, REF_FREE_LIMIT_5H, is_free=True)
        bar_free_w = render_model_quota_bar(tok_free_w, REF_FREE_LIMIT_WEEKLY, is_free=True)

        bar_low_5h = render_model_quota_bar(tok_low_5h, 3_300_000, is_free=False)
        bar_low_w = render_model_quota_bar(tok_low_w, 16_500_000, is_free=False)

        bar_prem_5h = render_model_quota_bar(tok_prem_5h, 1_900_000, is_free=False)
        bar_prem_w = render_model_quota_bar(tok_prem_w, 9_500_000, is_free=False)

        md.append("### 🟢 1. KATMAN ÖZETİ")
        md.append("| Katman | 5 Saatlik Doluluk | Haftalık Doluluk |")
        md.append("| :--- | :--- | :--- |")
        md.append(f"| 💎 Uzman Katman (Claude / Argon) | `{bar_prem_5h}` | `{bar_prem_w}` |")
        md.append(f"| ⚡ Düşük Kota İşçi (Flash / Codex) | `{bar_low_5h}` | `{bar_low_w}` |")
        md.append(f"| 🟢 Ücretsiz / Yerel (0 TL) | `{bar_free_5h}` | `{bar_free_w}` |")
        md.append("")

        # FİRMA / SAĞLAYICI GENEL KOTA TABLOSU (Kullanıcının talep ettiği firma ayrışımı)
        m_data_5h = self._aggregate_model_tokens(h5.get("_raw_events", []))
        m_data_w = self._aggregate_model_tokens(w.get("_raw_events", []))

        prov_5h = self._aggregate_provider_tokens(m_data_5h)
        prov_w = self._aggregate_provider_tokens(m_data_w)

        md.append("#### 🏢 Sağlayıcı & Firma Kotası Özeti")
        md.append("| Firma / Ekosistem | 5 Saatlik Doluluk | Haftalık Doluluk |")
        md.append("| :--- | :--- | :--- |")

        for p_key in ["anthropic", "openai", "google", "opensource"]:
            p_5h = prov_5h.get(p_key, {})
            p_w = prov_w.get(p_key, {})

            p_tok_5h = p_5h.get("tokens", 0)
            p_tok_w = p_w.get("tokens", 0)
            p_lim_5h = p_5h.get("limit_5h", REF_FREE_LIMIT_5H)
            p_lim_w = p_w.get("limit_w", REF_FREE_LIMIT_WEEKLY)
            p_is_free = p_5h.get("is_free", False)

            p_bar_5h = render_model_quota_bar(p_tok_5h, p_lim_5h, is_free=p_is_free)
            p_bar_w = render_model_quota_bar(p_tok_w, p_lim_w, is_free=p_is_free)
            p_label = p_5h.get("label", p_key)

            md.append(f"| {p_label} | `{p_bar_5h}` | `{p_bar_w}` |")

        md.append("")
        ratio_val = h5.get("free_and_worker_ratio", 0.0)
        saved_val = h5.get("estimated_saved_usd", 0.0)
        md.append(f"> 🛡️ **Kota Koruma Oranı:** %{ratio_val:.1f} | 💰 **Tahmini Tasarruf:** ${saved_val:.2f}")
        md.append("")
        md.append("---")
        md.append("")

        # 2. BÖLÜM: MODELLER VE EFORLAR (FİRMA BAZINDA DÜZENLENMİŞ, SADE 3 SÜTUNLU TABLOLAR)
        md.append("### 🤖 2. MODELLER VE EFORLAR (SAĞLAYICI BAZLI)")

        def get_tier_icon(tier: str) -> str:
            if tier == "free":
                return "🟢"
            elif tier == "low_quota":
                return "⚡"
            return "💎"

        # 4 Firma Grubu: Anthropic, OpenAI, Google, Açık Kaynak
        provider_groups = [
            ("anthropic", "🟣 Anthropic (Claude Ailesi)"),
            ("openai", "🟢 OpenAI Ailesi"),
            ("google", "🔵 Google (Gemini Ailesi)"),
            ("opensource", "🌐 Açık Kaynak & Yerel GPU (0 TL Ücretsiz Motorlar)"),
        ]

        for p_key, p_title in provider_groups:
            md.append(f"#### {p_title}")
            md.append("| Model ve Efor (Katman) | 5 Saatlik Doluluk | Haftalık Doluluk |")
            md.append("| :--- | :--- | :--- |")

            if p_key == "opensource":
                # Açık kaynak / 0 TL modelleri en çok kullanılandan en aza dinamik sıralı
                group_models = [m for m in self.FREE_REFERENCE_MODELS if m.get("provider") == "opensource"]
                group_models_sorted = sorted(
                    group_models,
                    key=lambda s: m_data_w.get(s["name"], {}).get("tokens", 0),
                    reverse=True,
                )
                for spec in group_models_sorted:
                    m_name = spec["name"]
                    tok_5h = m_data_5h.get(m_name, {}).get("tokens", 0)
                    tok_w = m_data_w.get(m_name, {}).get("tokens", 0)
                    lim_5h = spec.get("limit_5h", REF_FREE_LIMIT_5H)
                    lim_w = spec.get("limit_weekly", REF_FREE_LIMIT_WEEKLY)

                    bar_5h = render_model_quota_bar(tok_5h, lim_5h, is_free=True)
                    bar_w = render_model_quota_bar(tok_w, lim_w, is_free=True)
                    md.append(f"| 🟢 `{m_name} (0 TL)` | `{bar_5h}` | `{bar_w}` |")
            else:
                # Ücretli modeller en ağır kotadan aşağıya sabit sıralı
                paid_in_group = [m for m in self.PAID_REFERENCE_MODELS if m.get("provider") == p_key]
                # Eğer Google grubundaysa Flash-Lite modellerini de ekle
                if p_key == "google":
                    free_in_google = [m for m in self.FREE_REFERENCE_MODELS if m.get("provider") == "google"]
                else:
                    free_in_google = []

                for spec in paid_in_group:
                    m_name = spec["name"]
                    tok_5h = m_data_5h.get(m_name, {}).get("tokens", 0)
                    tok_w = m_data_w.get(m_name, {}).get("tokens", 0)
                    lim_5h = spec["limit_5h"]
                    lim_w = spec["limit_weekly"]

                    bar_5h = render_model_quota_bar(tok_5h, lim_5h, is_free=False)
                    bar_w = render_model_quota_bar(tok_w, lim_w, is_free=False)
                    icon = get_tier_icon(spec["tier"])
                    md.append(f"| {icon} `{m_name}` | `{bar_5h}` | `{bar_w}` |")

                for spec in free_in_google:
                    m_name = spec["name"]
                    tok_5h = m_data_5h.get(m_name, {}).get("tokens", 0)
                    tok_w = m_data_w.get(m_name, {}).get("tokens", 0)
                    lim_5h = spec.get("limit_5h", REF_FREE_LIMIT_5H)
                    lim_w = spec.get("limit_weekly", REF_FREE_LIMIT_WEEKLY)

                    bar_5h = render_model_quota_bar(tok_5h, lim_5h, is_free=True)
                    bar_w = render_model_quota_bar(tok_w, lim_w, is_free=True)
                    md.append(f"| 🟢 `{m_name} (0 TL)` | `{bar_5h}` | `{bar_w}` |")

            md.append("")

        md.append("---")
        md.append("")

        # 3. BÖLÜM: CLI ARAÇLARI
        md.append("### 🛠️ 3. CLI ARAÇLARI")
        md.append("| CLI Aracı (Katman) | 5 Saatlik Doluluk | Haftalık Doluluk |")
        md.append("| :--- | :--- | :--- |")

        cli_5h_tokens = self._aggregate_cli_tokens(h5.get("_raw_events", []))
        cli_w_tokens = self._aggregate_cli_tokens(w.get("_raw_events", []))

        paid_clis = ["ClaudeCode", "Codex", "Antigravity"]
        free_clis = ["4KWorkstation", "TestRunner", "OpenCode", "Hermes", "YerelOllama"]

        sorted_free_clis = sorted(free_clis, key=lambda c: cli_w_tokens.get(c, {}).get("tokens", 0), reverse=True)
        ordered_clis = paid_clis + sorted_free_clis

        for c_name in ordered_clis:
            tok_5h = cli_5h_tokens.get(c_name, {}).get("tokens", 0)
            tok_w = cli_w_tokens.get(c_name, {}).get("tokens", 0)

            c_lower = c_name.lower()
            if "antigravity" in c_lower:
                lim_5h, lim_w, is_free = 1_500_000, 7_500_000, False
                label = "💎 `Antigravity (agy.exe)` • 🔵 Google"
            elif "claude" in c_lower:
                lim_5h, lim_w, is_free = 400_000, 2_000_000, False
                label = "💎 `ClaudeCode` • 🟣 Anthropic"
            elif "codex" in c_lower:
                lim_5h, lim_w, is_free = 800_000, 4_000_000, False
                label = "⚡ `Codex` • 🟢 OpenAI"
            elif "ollama" in c_lower:
                lim_5h, lim_w, is_free = REF_FREE_LIMIT_5H, REF_FREE_LIMIT_WEEKLY, True
                label = "🟢 `YerelOllama (0 TL)` • 🖥️ RTX 5070 Ti"
            elif "opencode" in c_lower:
                lim_5h, lim_w, is_free = REF_FREE_LIMIT_5H, REF_FREE_LIMIT_WEEKLY, True
                label = "🟢 `OpenCode (0 TL)` • 🌐 Açık Kaynak"
            elif "hermes" in c_lower:
                lim_5h, lim_w, is_free = REF_FREE_LIMIT_5H, REF_FREE_LIMIT_WEEKLY, True
                label = "🟢 `Hermes (0 TL)` • 🌐 Açık Kaynak"
            elif "testrunner" in c_lower:
                lim_5h, lim_w, is_free = REF_FREE_LIMIT_5H, REF_FREE_LIMIT_WEEKLY, True
                label = "🟢 `TestRunner (0 TL)` • 💻 Python Test"
            else:
                lim_5h, lim_w, is_free = REF_FREE_LIMIT_5H, REF_FREE_LIMIT_WEEKLY, True
                label = f"🟢 `{c_name} (0 TL)` • ⚡ Yerel Motor"

            bar_5h = render_model_quota_bar(tok_5h, lim_5h, is_free=is_free)
            bar_w = render_model_quota_bar(tok_w, lim_w, is_free=is_free)

            md.append(f"| {label} | `{bar_5h}` | `{bar_w}` |")

        md.append("")
        md.append("---")
        md.append("")

        # 4. BÖLÜM: AJANLAR VE KULLANDIKLARI MODELLER
        md.append("### 🕵️ 4. AJANLAR VE KULLANDIKLARI MODELLER")
        md.append("| Ajan Rolü | Sağlayıcı ve Model | 5 Saatlik Doluluk | Haftalık Doluluk |")
        md.append("| :--- | :--- | :--- | :--- |")

        ag_5h_tokens = self._aggregate_agent_tokens(h5.get("_raw_events", []))
        ag_w_tokens = self._aggregate_agent_tokens(w.get("_raw_events", []))

        all_agent_keys = set(ag_5h_tokens.keys()).union(ag_w_tokens.keys())
        if all_agent_keys:
            sorted_agent_keys = sorted(
                all_agent_keys,
                key=lambda k: ag_w_tokens.get(k, ag_5h_tokens.get(k, {})).get("tokens", 0),
                reverse=True,
            )
            for k in sorted_agent_keys:
                entry_5h = ag_5h_tokens.get(k, {})
                entry_w = ag_w_tokens.get(k, {})
                meta = entry_w if entry_w else entry_5h

                ag_name = meta.get("agent_name", k)
                m_name = meta.get("model_name", "Gemini 3.8 Flash (Medium)")
                tier = meta.get("tier", "free")
                provider = meta.get("provider", "opensource")
                is_free = meta.get("is_free", True)
                lim_5h = meta.get("limit_5h", REF_FREE_LIMIT_5H)
                lim_w = meta.get("limit_weekly", REF_FREE_LIMIT_WEEKLY)

                tok_5h = entry_5h.get("tokens", 0)
                tok_w = entry_w.get("tokens", 0)

                icon = get_tier_icon(tier)
                p_info = self.PROVIDERS.get(provider, {"color": "🌐", "name": "Açık Kaynak"})
                p_icon = p_info.get("color", "🌐")

                m_label = f"{icon} {p_icon} `{m_name} (0 TL)`" if is_free else f"{icon} {p_icon} `{m_name}`"
                bar_5h = render_model_quota_bar(tok_5h, lim_5h, is_free=is_free)
                bar_w = render_model_quota_bar(tok_w, lim_w, is_free=is_free)
                md.append(f"| {ag_name} | {m_label} | `{bar_5h}` | `{bar_w}` |")
        else:
            md.append("| *Henüz kayıtlı alt ajan görevi bulunmuyor.* | `-` | `[░░░░░░░░░░░░░░░░░░░░] %0.0` | `[░░░░░░░░░░░░░░░░░░░░] %0.0` |")

        md.append("")
        md.append("---")
        md.append("🎯 **4K AI WORKSTATION:** Sistem 7/24 yerel ve bulut kaynaklarınızı optimize ederek bütçenizi ve kotanızı korur.")

        return "\n".join(md)

