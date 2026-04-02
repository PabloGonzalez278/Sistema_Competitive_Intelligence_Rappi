"""
Tests básicos para el sistema de Competitive Intelligence.
"""
import json
import sys
from pathlib import Path

import pytest

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import CONFIG_DIR, DATA_DIR
from scrapers.base_scraper import ScrapingResult
from analysis.analyzer import CompetitiveAnalyzer


class TestConfiguration:
    """Tests de configuración."""

    def test_addresses_file_exists(self):
        assert (CONFIG_DIR / "addresses.json").exists()

    def test_products_file_exists(self):
        assert (CONFIG_DIR / "products.json").exists()

    def test_addresses_structure(self):
        with open(CONFIG_DIR / "addresses.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "addresses" in data
        assert len(data["addresses"]) >= 20
        for addr in data["addresses"]:
            assert "id" in addr
            assert "name" in addr
            assert "address" in addr
            assert "lat" in addr
            assert "lng" in addr
            assert "zone_type" in addr

    def test_products_structure(self):
        with open(CONFIG_DIR / "products.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "categories" in data
        assert "fast_food" in data["categories"]
        assert "retail" in data["categories"]

    def test_zone_type_coverage(self):
        with open(CONFIG_DIR / "addresses.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        zones = {addr["zone_type"] for addr in data["addresses"]}
        # Debe cubrir al menos 4 tipos de zona
        assert len(zones) >= 4

    def test_data_directory_exists(self):
        assert DATA_DIR.exists()


class TestScrapingResult:
    """Tests del modelo de datos."""

    def test_scraping_result_creation(self):
        address = {
            "id": "test_01",
            "name": "Test Address",
            "address": "Calle Test 123",
            "zone_type": "premium",
            "lat": 19.43,
            "lng": -99.13,
        }
        result = ScrapingResult("rappi", address, "2025-01-01_12-00-00")
        assert result.platform == "rappi"
        assert result.address_id == "test_01"
        assert result.zone_type == "premium"

    def test_scraping_result_to_dict(self):
        address = {
            "id": "test_01",
            "name": "Test",
            "address": "Test 123",
            "zone_type": "middle",
            "lat": 19.43,
            "lng": -99.13,
        }
        result = ScrapingResult("uber_eats", address, "2025-01-01_12-00-00")
        result.products.append({"store_name": "McDonalds", "products": []})
        result.fees = {"McDonalds": {"delivery_fee": 29.0}}

        d = result.to_dict()
        assert d["platform"] == "uber_eats"
        assert len(d["products"]) == 1
        assert "McDonalds" in d["fees"]


class TestAnalyzer:
    """Tests del motor de análisis."""

    @pytest.fixture
    def sample_results(self):
        return {
            "rappi": [
                {
                    "platform": "rappi",
                    "address_id": "addr_01",
                    "address_name": "Polanco",
                    "zone_type": "premium",
                    "products": [
                        {
                            "store_name": "McDonald's",
                            "products": [
                                {"product_id": "ff_01", "product_name": "Big Mac", "found": True, "price": 99.0, "available": True},
                                {"product_id": "ff_02", "product_name": "Combo Big Mac", "found": True, "price": 169.0, "available": True},
                            ],
                            "estimated_delivery_time": "25-35 min",
                        }
                    ],
                    "fees": {"McDonald's": {"delivery_fee": 29.0, "service_fee": 15.0}},
                    "promotions": [{"platform": "rappi", "type": "discount", "description": "20% off primer pedido"}],
                    "errors": [],
                }
            ],
            "uber_eats": [
                {
                    "platform": "uber_eats",
                    "address_id": "addr_01",
                    "address_name": "Polanco",
                    "zone_type": "premium",
                    "products": [
                        {
                            "store_name": "McDonald's",
                            "products": [
                                {"product_id": "ff_01", "product_name": "Big Mac", "found": True, "price": 89.0, "available": True},
                                {"product_id": "ff_02", "product_name": "Combo Big Mac", "found": True, "price": 159.0, "available": True},
                            ],
                            "estimated_delivery_time": "20-30 min",
                        }
                    ],
                    "fees": {"McDonald's": {"delivery_fee": 19.0, "service_fee": 12.0}},
                    "promotions": [
                        {"platform": "uber_eats", "type": "discount", "description": "2x1 en combos"},
                        {"platform": "uber_eats", "type": "promotion", "description": "Envío gratis +$200"},
                    ],
                    "errors": [],
                }
            ],
            "didi_food": [
                {
                    "platform": "didi_food",
                    "address_id": "addr_01",
                    "address_name": "Polanco",
                    "zone_type": "premium",
                    "products": [
                        {
                            "store_name": "McDonald's",
                            "products": [
                                {"product_id": "ff_01", "product_name": "Big Mac", "found": True, "price": 95.0, "available": True},
                                {"product_id": "ff_02", "product_name": "Combo Big Mac", "found": True, "price": 165.0, "available": True},
                            ],
                            "estimated_delivery_time": "30-40 min",
                        }
                    ],
                    "fees": {"McDonald's": {"delivery_fee": 25.0, "service_fee": 10.0}},
                    "promotions": [],
                    "errors": [],
                }
            ],
        }

    def test_analyzer_creation(self, sample_results):
        analyzer = CompetitiveAnalyzer(sample_results)
        assert len(analyzer.platforms) == 3

    def test_full_analysis_structure(self, sample_results):
        analyzer = CompetitiveAnalyzer(sample_results)
        analysis = analyzer.run_full_analysis()

        assert "summary" in analysis
        assert "price_comparison" in analysis
        assert "fee_comparison" in analysis
        assert "delivery_time_comparison" in analysis
        assert "promotion_analysis" in analysis
        assert "geographic_analysis" in analysis
        assert "top_insights" in analysis
        assert len(analysis["top_insights"]) == 5

    def test_price_comparison(self, sample_results):
        analyzer = CompetitiveAnalyzer(sample_results)
        analysis = analyzer.run_full_analysis()
        prices = analysis["price_comparison"]
        assert len(prices) > 0
        for key, data in prices.items():
            assert "cheapest_platform" in data
            assert "prices_by_platform" in data

    def test_fee_comparison(self, sample_results):
        analyzer = CompetitiveAnalyzer(sample_results)
        analysis = analyzer.run_full_analysis()
        fees = analysis["fee_comparison"]
        assert "rappi" in fees
        assert "uber_eats" in fees
        assert fees["rappi"]["delivery_fee"]["avg"] == 29.0
        assert fees["uber_eats"]["delivery_fee"]["avg"] == 19.0

    def test_insights_have_required_fields(self, sample_results):
        analyzer = CompetitiveAnalyzer(sample_results)
        analysis = analyzer.run_full_analysis()
        for insight in analysis["top_insights"]:
            assert "finding" in insight
            assert "impact" in insight
            assert "recommendation" in insight
            assert "category" in insight

    def test_delivery_time_extraction(self, sample_results):
        analyzer = CompetitiveAnalyzer(sample_results)
        analysis = analyzer.run_full_analysis()
        times = analysis["delivery_time_comparison"]
        assert "rappi" in times
        # "25-35 min" -> avg 30
        assert times["rappi"]["avg_minutes"] == 30.0
