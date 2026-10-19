# Reproduce every PlanArena result from public data.
#   make reproduce      full run on a clean clone (downloads about 17 GB; several hours on a laptop)
#   make results        rerun the models and validation on data already downloaded
#   make compare        list result files that differ from the committed ones
#   (a reproduction in another folder:  python -I -m planarena.tools.compare_results <folder>)
# Needs Python 3.13, curl, poppler (pdftotext, pdfinfo, pdftoppm) and Node 20+ for the web app.
# Downloaded data is untrusted: every step that reads it runs Python in isolated mode (-I).

PYTHON ?= python3.13   # the version requirements.txt is pinned for
PY  := .venv/bin/python -I
RUN := PYTHONWARNINGS=ignore $(PY) -m

.PHONY: reproduce results venv fetch twin history calibrate train transition rolling ablation vote validate report test web compare cities city screenshots

reproduce: venv fetch twin history calibrate results web test compare

results: train transition rolling ablation vote cities validate report

venv:
	test -x .venv/bin/python || $(PYTHON) -m venv .venv
	.venv/bin/pip install -q -r requirements.txt
	.venv/bin/python -c "import sysconfig,pathlib; pathlib.Path(sysconfig.get_paths()['purelib'],'planarena_repo.pth').write_text('$(CURDIR)\n')"

fetch:
	$(RUN) planarena.twin.fetch
	$(RUN) planarena.tools.fetch_open_data

twin:
	$(RUN) planarena.twin.build

# Annual twins 2015-2024 for the rolling-origin tests. The 2015 and 2020 twins are also used, with model
# outputs added, by the transition model and the change-prediction tests.
history:
	$(RUN) planarena.models.history
	for v in 15v1 20v8; do mkdir -p data/processed_$$v && cp data/history/$$v/parcels.parquet data/history/$$v/parcels.geoparquet data/history/$$v/graph.npz data/history/$$v/twin_meta.json data/processed_$$v/; done

calibrate:
	$(RUN) planarena.calibrate

train:
	$(RUN) planarena.models.train

transition:
	$(RUN) planarena.models.transition all

rolling:
	$(RUN) planarena.models.rolling

ablation:
	$(RUN) planarena.models.ablation all

vote:
	$(RUN) planarena.agents.voting
	$(PY) -c "from planarena.agents.voting import sensitivity_all_districts as f; f()"

CITY_LIST := "New York" "Los Angeles" Chicago Houston Phoenix Philadelphia "San Antonio" "San Diego" Dallas Milwaukee

# The ten cities from official parcel-level land use (Philadelphia's plan is digitised from its PDF district plans,
# then the city is rebuilt with it), their ingestion reports, and the cross-city and integration tests.
cities:
	for c in $(CITY_LIST); do $(RUN) planarena.cities.build "$$c" || exit 1; done
	$(RUN) planarena.cities.adapters.philadelphia_plan
	$(RUN) planarena.cities.build Philadelphia
	for c in $(CITY_LIST); do $(RUN) planarena.cities.ingestion "$$c" > /dev/null || exit 1; done
	$(RUN) planarena.cities.ingestion --summary > /dev/null
	$(RUN) planarena.models.integration
	$(RUN) planarena.models.integration transfer
	$(RUN) planarena.models.integration profile
	$(RUN) planarena.cities.mke_history
	$(RUN) planarena.models.crosscity
	$(RUN) planarena.models.replay
	$(RUN) planarena.models.ablate_recs

# One city:  make city CITY="Chicago"
city:
	$(RUN) planarena.cities.build "$(CITY)"

validate:
	$(RUN) planarena.tools.latency
	$(RUN) planarena.validate all

report:
	$(RUN) planarena.report
	$(RUN) planarena.figures
	$(RUN) planarena.paper

web:
	cd web && npm ci && npx vite build

test:
	$(RUN) pytest -q

compare:
	git diff --stat -- results docs README.md planarena/indicators/calibrated.yaml

# Studio figures for the paper (needs Google Chrome)
screenshots:
	$(RUN) planarena.tools.screenshots
