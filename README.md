# New3

## Назначение проекта

Репозиторий содержит офлайн-комплекс разработки для Windows.  
Цель комплекса — развернуть на машине без доступа к сети готовую рабочую среду для:

- Python 3.13 и Jupyter Notebook
- обработки таблиц Excel и формирования DOCX-документов
- веб-разработки на Django / Flask / FastAPI
- упаковки Python-приложений
- работы в VS Code с уже подготовленными расширениями
- локальной работы с PostgreSQL 15, SQL Server Express и SSMS

## Из каких частей состоит комплекс

### 1. Системные установщики

Папка `installers/` содержит офлайн-установщики и вспомогательные скрипты для системных компонентов:

- Python 3.13
- Git for Windows
- Node.js
- PostgreSQL 15
- SQL Server 2022 Express
- SQL Server Management Studio (SSMS)
- Visual Studio Code

Для больших дистрибутивов используются split-части и скрипты восстановления полного установщика:

- `installers/vscode/`
- `installers/sqlserver/`
- `installers/postgresql/`

### 2. Python wheelhouse

Папка `wheelhouse/py313-windows-x86_64/` содержит офлайн-набор Python-пакетов для Windows x64 и Python 3.13.

В набор входят:

- data stack: `numpy`, `pandas`
- notebook stack: `notebook`, `ipykernel`
- plotting: `matplotlib`, `matplotlib-venn`
- DOCX / Excel: `python-docx`, `docxtpl`, `openpyxl`, `xlsxwriter`, `pyxlsb`, `lxml`, `pillow`
- packaging: `pyinstaller`, `auto-py-to-exe`
- web: `django`, `flask`, `fastapi`, `uvicorn`

### 3. VS Code extensions

Папка `vscode-extensions/` содержит офлайн VSIX-набор:

- Python
- Pylance
- Python Debugger
- Python Environments
- Jupyter и связанные расширения
- GitLens

### 4. Сценарии установки

В репозитории есть два основных способа установки:

- консольный:
  - `install-offline-dev-suite.ps1`
  - `install-offline-dev-suite.cmd`
- графический:
  - `install-offline-dev-suite-gui.ps1`
  - `install-offline-dev-suite-gui.cmd`

### 5. Документация и контекст

- `docs/offline-development-suite-documentation.docx` — подробная документация по комплексу
- `.cursor/rules/project-context.mdc` — проектный контекст для локального Cursor

## Что делает основной installer

Основной PowerShell installer:

- проверяет наличие и checksum офлайн-артефактов
- восстанавливает split-установщики при необходимости
- устанавливает системные компоненты
- глобально устанавливает Python-пакеты в Python 3.13
- регистрирует Jupyter kernel `Offline Dev Python 3.13`
- устанавливает VS Code extensions
- обновляет workspace-файл `.vscode/settings.json`, чтобы проект сразу указывал на ожидаемый Python interpreter
- обновляет `settings.json` VS Code:
  - `python.defaultInterpreterPath`
  - `jupyter.jupyterServerType=local`
- выводит версии ключевых инструментов в конце установки

## Порядок установки

### Рекомендуемый сценарий

1. Распаковать репозиторий на Windows-машине
2. Если нужны:
   - Node.js
   - PostgreSQL 15
   - SQL Server Express
   - SSMS
   
   запускать installer **из-под администратора**
3. Выбрать способ установки:
   - GUI: `install-offline-dev-suite-gui.cmd`
   - консоль: `install-offline-dev-suite.cmd`
4. Дождаться завершения установки
5. Открыть новый терминал, чтобы гарантированно подхватились обновленные PATH и shell integrations
6. Запустить VS Code
7. Проверить:
   - выбранный Python interpreter
   - доступность kernel `Offline Dev Python 3.13`

Если installer запускается от администратора и не задан пользовательский путь Python, Python 3.13 ставится для всех пользователей в:

```text
C:\Program Files\Python313
```

### Консольный запуск

PowerShell:

```powershell
.\install-offline-dev-suite.ps1
```

Command Prompt:

```bat
install-offline-dev-suite.cmd
```

### Графический запуск

PowerShell:

```powershell
.\install-offline-dev-suite-gui.ps1
```

Command Prompt:

```bat
install-offline-dev-suite-gui.cmd
```

## Что важно знать по отдельным компонентам

### Python-пакеты

Python-библиотеки устанавливаются **глобально** в установленный Python 3.13, а не в `.venv`.

### PostgreSQL 15

- installer восстанавливается из split-частей
- по умолчанию ставятся:
  - сервер
  - command line tools
  - pgAdmin
- `pgAdmin` можно пропустить отдельным флагом

### SQL Server Express

- installer тоже восстанавливается из split-частей
- установка выполняется в unattended-режиме

### SSMS

В репозитории хранится bootstrapper.  
Для полностью офлайн-установки SSMS рекомендуется заранее подготовить layout:

```powershell
.\installers\ssms\create-offline-layout.ps1
```

### VS Code

Installer включает:

- контекстное меню `Open with Code`
- file associations
- добавление в PATH

## Быстрые проверки после установки

```powershell
git --version
node --version
npm --version
python --version
python -m pip --version
python -m notebook --version
python -m django --version
python -m uvicorn --version
psql --version
```

## Статус проверки в CI

Windows workflow проверяет:

- checksum и rebuild установщиков
- установку Node.js
- установку PostgreSQL 15 и наличие pgAdmin
- установку Python и глобального wheelhouse
- импорт Python-стека
- web smoke-test для Django / Flask / FastAPI
- работу `uvicorn`
- PowerShell parser validation для installer-скриптов