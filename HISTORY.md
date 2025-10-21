# Development History

This document tracks the evolution of Tkonverter across releases and major refactors. It is migrated from the former "Development Story" section of README to keep the main page concise.

## Mid-late August 2025 — From script to refactored GUI

The journey of Tkonverter began as a personal script to convert Telegram chats, which quickly evolved into a full GUI application in one week using Google's Gemini. The initial rapid development, aimed at an MVP architecture, resulted in spaghetti code and race conditions that made further progress impossible.

A full-scale refactoring was necessary. Gemini outlined a plan, and CursorAI with Sonnet 4 rebuilt 80% of the app into a clean, dependency-injected model overnight. The final, tedious debugging phase took another 2-3 days with Gemini. This effort also resulted in a reusable Fluent Design UI toolkit for future projects.

## Early October 2025 — Shared toolkit, analysis overhaul, and CLI

With renewed access to Cursor AI, the codebase was unified with Improve-ImgSLI, creating a shared library, `shared_toolkit`. The most challenging part was a complete overhaul of the analysis system; its tree-based logic was rebuilt from scratch multiple times over 15 hours to handle complex data and matplotlib integration.

In stark contrast, the new architecture's power was proven when a full-featured CLI was added in just two minutes using CursorAI. It simply reused all existing core services, demonstrating how a proper separation of concerns enables rapid feature development without code duplication.
