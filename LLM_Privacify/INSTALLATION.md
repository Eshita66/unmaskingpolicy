# Installation and Usage

## Local model setup
Install and open LM Studio.

Use the model:
`meta-llama-3.1-8b-instruct`

In developer mode, ensure the local server is reachable at:
`http://127.0.0.1:5000`

### Optional
- Increase context length to around 8500 if needed
- Reload the model after changing load settings

## Environment setup
```bash
conda create -n privacify python=3.10 -y
conda activate privacify
cd LLM_Privacify
pip install -r requirements.txt

### Input configuration
Before running the script, set the input file path for the privacy policy links inside the script.

Example:
INPUT_FILE = "data/input/privacy_policy_links.txt"
### Run
python ppaf_scraper.py