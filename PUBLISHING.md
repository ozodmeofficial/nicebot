# Chiqarish

## Eng oson yo'l: bitta fayl

1. https://pypi.org da akkaunt oching va 2FA'ni yoqing. Keyin **Account settings → API tokens → Add API token** bo'limida "Entire account" doirasida token yarating. Birinchi yuklashdan keyin uni faqat `nicebot` loyihasiga cheklangan token bilan almashtirish tavsiya qilinadi.
2. Kompyuteringizda Python va Node.js o'rnatilgan bo'lsin.
3. Windows'da `deploy.bat` faylini ikki marta bosing. macOS yoki Linux'da `./deploy.sh` buyrug'ini ishga tushiring.
   - Token so'ralganda PyPI tokenini kiriting. U faqat sizning terminalingizda qoladi.
   - surge.sh birinchi marta email va parol so'raydi va akkauntni o'sha yerning o'zida ochadi.

---

# GitHub orqali (Trusted Publishing)

Bu usulda API kalit hech qayerda saqlanmaydi. PyPI GitHub Actions'ga to'g'ridan-to'g'ri ishonadi.

## 1. GitHub repo

1. GitHub'da `nicebot` nomli repo yarating.
2. Fayllardagi `OWNER` so'zini GitHub username'ingizga almashtiring (`pyproject.toml` va `README.md`):

   ```bash
   sed -i 's/OWNER/sizning_username/g' pyproject.toml README.md
   ```

3. Kodni yuklang:

   ```bash
   git init && git add . && git commit -m "nicebot 0.1.0"
   git branch -M main
   git remote add origin https://github.com/sizning_username/nicebot.git
   git push -u origin main
   ```

## 2. PyPI'da "pending publisher"

1. https://pypi.org ga kiring (akkaunt bo'lmasa, oching va 2FA'ni yoqing).
2. **Account settings → Publishing → Add a new pending publisher → GitHub** bo'limiga o'ting.
3. Maydonlarni to'ldiring:

   | Maydon | Qiymat |
   |---|---|
   | PyPI Project Name | `nicebot` |
   | Owner | GitHub username'ingiz |
   | Repository name | `nicebot` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

4. **Add** tugmasini bosing.

## 3. GitHub'da `pypi` environment

Repo → **Settings → Environments → New environment** → nomi: `pypi`. Xohlasangiz, "Required reviewers" qo'shing, shunda har bir chiqarishni qo'lda tasdiqlaysiz.

## 4. Chiqarish

Versiya tegini push qiling:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Actions bo'limida testlar 4 ta Python versiyasida PostgreSQL, MariaDB va Redis bilan ishga tushadi. Ular o'tsa, paket PyPI'ga avtomatik yuklanadi va `CHANGELOG.md` dagi yozuv bilan GitHub Release yaratiladi. Teg versiyasi `__about__.py` dagi versiya bilan bir xil bo'lishi shart.

## Keyingi versiyalar

1. `src/nicebot/__about__.py` faylidagi versiyani oshiring (masalan, `1.0.1`).
2. `CHANGELOG.md` ga `## 1.0.1 — sana` bo'limini yozing.
3. `main` ga push qiling, keyin teg: `git tag v1.0.1 && git push origin v1.0.1`.

## Hujjat sayti (GitHub Pages)

Repo → **Settings → Pages → Source: GitHub Actions**. `docs/` yoki `src/` o'zgarganda sayt `https://sizning_username.github.io/nicebot/` manzilida o'zi yangilanadi.

## Muqobil yo'l: qo'lda yuklash

`dist/` papkasida tayyor paket bor:

```bash
pip install twine
twine upload dist/*
```

Kalitni `twine` so'raganda faqat o'z kompyuteringizda kiriting.
