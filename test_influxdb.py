""" Pytest tests for the influxdb module """

import pytest

from influxdb import InfluxDbConfiguration


class TestInfluxDbConfiguration:
    def test_no_config(self):
        assert InfluxDbConfiguration.from_json_cfg(None) is None

    def test_empty_config(self):
        assert InfluxDbConfiguration.from_json_cfg(dict()) is None

    def test_no_url(self):
        cfg = {
            "influxdb": {}
        }
        with pytest.raises(ValueError) as e:
            InfluxDbConfiguration.from_json_cfg(cfg)
        assert "URL must be provided" in str(e.value)

    def test_no_token(self):
        cfg = {
            "influxdb": {
                "url": "http://localhost:8086"
            }
        }
        with pytest.raises(ValueError) as e:
            InfluxDbConfiguration.from_json_cfg(cfg)
        assert "token must be provided" in str(e.value)

    def test_no_org(self):
        cfg = {
            "influxdb": {
                "url": "http://localhost:8086",
                "token": "mytoken"
            }
        }
        with pytest.raises(ValueError) as e:
            InfluxDbConfiguration.from_json_cfg(cfg)
        assert "org must be provided" in str(e.value)

    def test_required_fields_no_bucket(self):
        cfg = {
            "influxdb": {
                "url": "http://localhost:8086",
                "token": "mytoken",
                "org": "myorg"
            }
        }
        influx_cfg = InfluxDbConfiguration.from_json_cfg(cfg)

        assert influx_cfg.url() == "http://localhost:8086"
        assert influx_cfg.token() == "mytoken"
        assert influx_cfg.org() == "myorg"
        assert influx_cfg.bucket() is None

    def test_all_fields(self):
        cfg = {
            "influxdb": {
                "url": "http://influx.example.com:8086",
                "token": "secret-token",
                "org": "myorg",
                "bucket": "mybucket"
            }
        }
        influx_cfg = InfluxDbConfiguration.from_json_cfg(cfg)

        assert influx_cfg.url() == "http://influx.example.com:8086"
        assert influx_cfg.token() == "secret-token"
        assert influx_cfg.org() == "myorg"
        assert influx_cfg.bucket() == "mybucket"

    def test_direct_construction_missing_url(self):
        with pytest.raises(ValueError) as e:
            InfluxDbConfiguration(url=None, token="t", org="o")
        assert "URL must be provided" in str(e.value)

    def test_direct_construction_missing_token(self):
        with pytest.raises(ValueError) as e:
            InfluxDbConfiguration(url="http://localhost:8086", token=None, org="o")
        assert "token must be provided" in str(e.value)

    def test_direct_construction_missing_org(self):
        with pytest.raises(ValueError) as e:
            InfluxDbConfiguration(url="http://localhost:8086", token="t", org=None)
        assert "org must be provided" in str(e.value)
