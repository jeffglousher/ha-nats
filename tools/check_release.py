"""Run from repository root; requires PyYAML 6.0.3."""
from pathlib import Path
import re, yaml
root=Path(__file__).resolve().parents[1]
configs=list(root.glob('*/config.yaml'));assert len(configs)==1
folder=configs[0].parent
config=yaml.safe_load(configs[0].read_text())
assert re.fullmatch(r'\d+\.\d+\.\d+',config['version'])
assert set(config['arch'])=={'amd64','aarch64'}
assert config['backup']=='cold' and config['boot']=='auto'
for flag in ['host_network','homeassistant_api','docker_api','full_access','privileged']:
    assert not config.get(flag),flag
assert config.get('hassio_api') and config.get('hassio_role') == 'default'
for path in ['LICENSE','SECURITY.md','CONTRIBUTING.md','THIRD_PARTY.md','RELEASING.md','repository.yaml']:
    assert (root/path).is_file(),path
for path in ['README.md','DOCS.md','CHANGELOG.md','icon.png','logo.png','run.sh','Dockerfile','tests/runtime.py']:
    assert (folder/path).is_file(),path
translated=yaml.safe_load((folder/'translations/en.yaml').read_text())
assert set(translated['configuration'])==set(config['schema'])==set(config['options'])
assert config['version'] in (folder/'CHANGELOG.md').read_text()
if config['name']=='NUI':
    assert config['ingress'] and config['ingress_port']==8099
    assert 'ports' not in config and 'webui' not in config
    assert config['watchdog'].endswith('/health')
else:
    assert not config.get('ingress') and 'webui' not in config
    assert config['map']==[{'type': 'ssl', 'read_only': True}]
    assert config['schema']['token']=='password'
    assert 'restore_mode' not in config['options']
    assert 'console_admin_user_ids' not in config['options']
    assert set(config['ports'])=={'4222/tcp'}
docker=(folder/'Dockerfile').read_text()
for line in docker.splitlines():
    if line.startswith('FROM ') and '/' in line or line.startswith(('FROM nats:','FROM golang:')):
        assert '@sha256:' in line,line
print('PASS: release files, version, translations, minimal privileges, pinned inputs and generic documentation')

for workflow in (root/'.github/workflows').glob('*.yaml'):
    document=yaml.load(workflow.read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
    assert isinstance(document,dict) and isinstance(document.get('jobs'),dict),workflow
    assert 'on' in document,workflow
print('PASS: workflow YAML parses; run actionlint for full semantic validation')
