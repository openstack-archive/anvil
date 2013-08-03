DOWNLOADS_DIR := $DOWNLOADS_DIR
LOGS_DIR := $LOGS_DIR
PY2RPM := $PY2RPM
PY2RPM_FLAGS := $PY2RPM_FLAGS

#raw
MARKS := $(foreach archive,$(shell ls $(DOWNLOADS_DIR)),$(archive).mark)


all: $(MARKS)


%.mark: $(DOWNLOADS_DIR)/%
	@echo "Building source rpm for $^"
	@echo "Output for build being placed in $(LOGS_DIR)/py2rpm-$*.log"
	@$(PY2RPM) $(PY2RPM_FLAGS) -- $^ &> $(LOGS_DIR)/py2rpm-$*.log
	@touch "$@"
	@echo "Created $*"
#end raw
