# P16 Environment Setup — CachyOS (i7 / 16GB RAM / 8GB NVIDIA VRAM)

Setup for the hybrid IaC misconfiguration pipeline: Terraform corpus → Checkov/tfsec → OPA/Rego → local LLM with citation gate.

> **Update:** using the Gemini API instead of a local model, so Steps 2–3 and 6 (NVIDIA driver, CUDA, Ollama) below are no longer required for the LLM piece — your GPU won't be doing inference work. Keep the driver installed anyway if you use the GPU for anything else, but you can skip straight to Step 4 if this is a fresh machine. Step 6 has been replaced with Gemini API setup.

**Hardware notes:**
- With inference happening in the cloud, your 16GB RAM / 8GB VRAM box is more than enough for everything else in the pipeline (Terraform, OPA, Checkov, tfsec, Python orchestration).

---

## Step 1 — System update & base packages
```bash
sudo pacman -Syu
sudo pacman -S --needed base-devel git python python-pip unzip curl jq
```

If you don't already have an AUR helper (CachyOS doesn't ship one by default on all editions):
```bash
which paru || (cd /tmp && git clone https://aur.archlinux.org/paru.git && cd paru && makepkg -si)
```

## Step 2 — NVIDIA driver
```bash
sudo pacman -S nvidia-open-dkms nvidia-utils nvidia-settings lib32-nvidia-utils
sudo reboot
```
> Use `nvidia-dkms` instead of `nvidia-open-dkms` if your card is pre-Turing (GTX 16-series or older).

Verify after reboot:
```bash
nvidia-smi
```
You should see your GPU listed with ~8GB total memory.

## Step 3 — CUDA toolkit
Needed for GPU-accelerated inference:
```bash
sudo pacman -S cuda cudnn
nvcc --version
```

## Step 4 — Terraform, Checkov, tfsec
```bash
paru -S terraform
terraform -version

pip install --user checkov
checkov --version

paru -S tfsec
tfsec --version
```

## Step 5 — OPA + Conftest (deterministic policy engine)
```bash
paru -S opa conftest
opa version
conftest --version
```
If either isn't in the AUR, grab the binary release directly from their GitHub releases pages and drop it in `/usr/local/bin`.

## Step 6 — Gemini API (contextual LLM engine)
1. Get an API key from https://aistudio.google.com/apikey (free tier is fine for a class project, but check current rate limits there — they change).
2. Store it as an environment variable rather than hardcoding it anywhere:
```bash
echo 'export GEMINI_API_KEY="your-key-here"' >> ~/.bashrc
source ~/.bashrc
```
3. Install the SDK inside your project's virtualenv (see Step 7):
```bash
pip install google-generativeai
```
4. Confirm the key works — this is your "deployed instance" evidence for the rubric:
```bash
python3 -c "
import google.generativeai as genai, os
genai.configure(api_key=os.environ['GEMINI_API_KEY'])
model = genai.GenerativeModel('gemini-2.0-flash')
print(model.generate_content('Say hello').text)
"
```
> Model names on Gemini change over time — if `gemini-2.0-flash` errors as unavailable, check https://ai.google.dev/gemini-api/docs/models for the current list.

## Step 7 — Python orchestration environment
```bash
python -m venv ~/p16-env
source ~/p16-env/bin/activate
pip install google-generativeai pyyaml pandas python-hcl2 tqdm checkov
```

## Step 8 — Project folder structure
```
p16-hybrid-iac/
├── corpus/       # Terraform test cases: simple + complex misconfigs
├── policies/     # Rego policy files (CIS-mapped)
├── baseline/     # Checkov/tfsec + ungrounded LLM outputs
├── pipeline/     # hybrid pipeline scripts (scan → OPA → LLM → gate)
├── results/      # metrics CSVs, evidence screenshots
└── README.md
```

## Step 9 — Capture "environment runs" evidence
The rubric requires proof, not slides. Screenshot or log each of these:
- The Gemini API test call from Step 6 returning a real response
- `checkov --version` and `tfsec --version` output
- `conftest test --policy policies/ plan.json` passing on a sample plan

## Step 10 — End-to-end sanity check
```bash
terraform init && terraform plan -out=plan.bin
terraform show -json plan.bin > plan.json

conftest test --policy policies/ plan.json
checkov -d .
tfsec .
```
If all four run without errors, your environment is ready to start building the hybrid pipeline and collecting baseline numbers.

---

## Troubleshooting
- **`nvidia-smi` not found / fails after driver install** → reboot, then check `dmesg | grep -i nvidia` for load errors. (Only matters if you're using the GPU for something else — Gemini calls don't touch it.)
- **Gemini call fails with an auth error** → double check `echo $GEMINI_API_KEY` actually prints your key in the shell you're running from; `.bashrc` changes don't apply to already-open terminals.
- **Gemini call fails with a model-not-found error** → the model name has likely changed; check https://ai.google.dev/gemini-api/docs/models and set `export GEMINI_MODEL="whatever-is-current"`.
- **AUR package build fails** → make sure `base-devel` is installed and you're running `makepkg` as a normal user, not root.
