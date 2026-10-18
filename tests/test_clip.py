from redteam.cli import main

def test_main_zero():
    result = main()
    assert result == 0 
