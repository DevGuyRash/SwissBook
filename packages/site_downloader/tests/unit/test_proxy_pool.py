from site_downloader.proxy import pool

def test_cycle_from_single_proxy():
    """Test that a single proxy cycles correctly."""
    rot = pool(single="http://proxy1:8080")
    assert next(rot) == "http://proxy1:8080"
    assert next(rot) == "http://proxy1:8080"  # Should keep returning the same proxy

def test_cycle_from_csv():
    """Test cycling through multiple proxies from a CSV string."""
    rot = pool(csv="http://proxy1:8080,http://proxy2:8080")
    assert next(rot) == "http://proxy1:8080"
    assert next(rot) == "http://proxy2:8080"
    assert next(rot) == "http://proxy1:8080"  # Should cycle back to the beginning

def test_cycle_from_file(tmp_path):
    """Test cycling through proxies from a file."""
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("http://proxy1:8080\nhttp://proxy2:8080\n")
    
    rot = pool(list_file=proxy_file)
    assert next(rot) == "http://proxy1:8080"
    assert next(rot) == "http://proxy2:8080"
    assert next(rot) == "http://proxy1:8080"  # Should cycle back to the beginning

def test_no_proxies():
    """Test behavior when no proxies are provided."""
    rot = pool()
    assert next(rot) is None
    assert next(rot) is None  # Should keep returning None
