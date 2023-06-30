import pytest


@pytest.fixture
def deployer(accounts):
    return accounts[0]


@pytest.fixture
def sender(accounts):
    return accounts[1]


@pytest.fixture
def recipient(accounts):
    return accounts[2]


@pytest.fixture
def solady(project, deployer, sender):
    solady = project.SoladyToken.deploy(sender=deployer)
    solady.transfer(sender, 10000, sender=deployer)
    return solady

@pytest.fixture
def vypertoken(project, deployer, sender):
    vypertoken = project.VyperToken.deploy(sender=deployer)
    vypertoken.transfer(sender, 10000, sender=deployer)
    return vypertoken

@pytest.fixture
def oztoken(project, deployer, sender):
    oztoken = project.OZToken.deploy(sender=deployer)
    oztoken.transfer(sender, 10000, sender=deployer)
    return oztoken

@pytest.fixture
def tokens(solady, vypertoken, oztoken):
    return solady, vypertoken, oztoken

def test_tokens(tokens, sender, recipient):
    for token in tokens:
        assert token.balanceOf(sender) == 10000
        assert token.balanceOf(recipient) == 0
        token.transfer(recipient, 1000, sender=sender)
        assert token.balanceOf(sender) == 9000
        assert token.balanceOf(recipient) == 1000

        # test allowance
        assert token.allowance(sender, recipient) == 0
        token.approve(recipient, 1000, sender=sender)
        assert token.allowance(sender, recipient) == 1000
        token.transferFrom(sender, recipient, 1000, sender=recipient)
        assert token.balanceOf(sender) == 8000
        assert token.balanceOf(recipient) == 2000
        assert token.allowance(sender, recipient) == 0

def test_solady(solady, sender, recipient):
    assert solady.balanceOf(sender) == 10000
    assert solady.balanceOf(recipient) == 0
    solady.transfer(recipient, 1000, sender=sender)
    assert solady.balanceOf(sender) == 9000
    assert solady.balanceOf(recipient) == 1000

    # test allowance
    assert solady.allowance(sender, recipient) == 0
    solady.approve(recipient, 1000, sender=sender)
    assert solady.allowance(sender, recipient) == 1000
    solady.transferFrom(sender, recipient, 1000, sender=recipient)
    assert solady.balanceOf(sender) == 8000
    assert solady.balanceOf(recipient) == 2000
    assert solady.allowance(sender, recipient) == 0
