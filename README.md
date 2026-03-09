# Disclosure Divergence

## Overview
This repository contains the artifact for a multi-stage pipeline designed to analyze privacy disclosures in Android applications by combining privacy policy analysis, Google Play Data Safety Label collection, dataset preparation, and downstream result analysis.


## Repository Structure

```text
 Disclosure Divergence/
├── README.md
├── LICENSE
├── .gitignore
├── LLM_Privacify/
├── DataSafetyScrapping/
├── DataAnalysis/
└── Datasets/

Component Description

LLM_Privacify/
Contains the privacy policy analysis pipeline. This module uses a local LLM-based workflow to process privacy policies and extract structured information for downstream comparison.

DataSafetyScrapping/
Contains scripts for collecting Google Play Data Safety Label URLs, scraping app-level data safety information, and extracting privacy policy links.

DataAnalysis/
Contains analysis scripts used for result preparation, metric computation, aggregation, and figure/table generation.

Datasets/
Contains input datasets.
