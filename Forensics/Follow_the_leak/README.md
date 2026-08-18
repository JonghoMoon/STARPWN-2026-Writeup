# Follow the leak

| | |
|---|---|
| **Category** | Forensics |
| **Points** | 451 |
| **Solves** | 177 |

## Description

You've been tasked to help Meridian follow one of their leads on their latest breach. Incidence response believes that the point of entry originated from information somewhere within this archive, but so far they've come out empty handed.

More info in the file, help them recover the hidden key.

**Attachments:** `opensatkit-badpush-student.zip`

I did not upload this file because it exceeds 600 MB. Please contact me privately if you need the original file.

## Solution

### Steps

**1. Extract and inspect the archive**

Unzip `opensatkit-badpush-student.zip` to reveal a git repository (`opensatkit-badpush-student/student/`). The challenge hints that a credential was leaked somewhere in the repo's history.

**2. Enumerate the full commit history**

Use `git log` to list all commits across all branches:

```bash
git log --all --oneline --decorate -30
```

A suspicious commit stands out immediately:

```
9967456c cosmos:temp lab key
```

**3. Inspect the suspicious commit**

```bash
git show --stat --summary 9967456c
```

The commit added a file `cosmos/.cdskeyfile` with the comment `# NOTE: TEMPORARY — remove before flight`.

**4. Retrieve the leaked key**

```bash
git show 9967456c:cosmos/.cdskeyfile
```

Output:
```
# NOTE: TEMPORARY — remove before flight
CDS_KEY=ZmxhZ3s1MHJyeV9XMTVoX1czX0MwdWxkX0cwXzcwXzdoM19NMDBuXzcwZzM3aDNyfQ==
```

**5. Decode the Base64 value**

```bash
echo "ZmxhZ3s1MHJyeV9XMTVoX1czX0MwdWxkX0cwXzcwXzdoM19NMDBuXzcwZzM3aDNyfQ==" | base64 -d
flag{50rry_W15h_W3_C0uld_G0_70_7h3_M00n_70g37h3r}
```

The decoded value is the flag.

## Flag

```
flag{50rry_W15h_W3_C0uld_G0_70_7h3_M00n_70g37h3r}
```
