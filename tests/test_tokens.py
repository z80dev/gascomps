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
    solady.transfer(sender, 10000000, sender=deployer)
    return solady

@pytest.fixture
def vypertoken(project, deployer, sender):
    vypertoken = project.VyperToken.deploy(sender=deployer)
    vypertoken.transfer(sender, 10000000, sender=deployer)
    return vypertoken

@pytest.fixture
def oztoken(project, deployer, sender):
    oztoken = project.OZToken.deploy(sender=deployer)
    oztoken.transfer(sender, 10000000, sender=deployer)
    return oztoken

@pytest.fixture
def weth9(project, deployer, sender):
    print("weth9")
    weth9 = project.WETH9.deploy(sender=deployer)
    print("weth9", weth9)
    project.provider.set_balance(deployer.address, 10000 * 10 ** 18)
    deployer.transfer(weth9, 1000 * 10 ** 18)

    weth9.transfer(sender, 10000000, sender=deployer)
    return weth9

@pytest.fixture
def dasytoken(project, deployer, sender):
    dasytoken = project.DasyToken.deploy("DasyToken", "DSY", 18, 1000 * 10 ** 18, sender=deployer)
    dasytoken.transfer(sender, 10000000, sender=deployer)
    return dasytoken

@pytest.fixture
def snekmate(project, deployer, sender):
    snekmate = project.Snekmate.deploy("Snekmate", "SNEK", 1000 * 10 ** 18, "GasComps", "v0.0.1", sender=deployer)
    snekmate.transfer(sender, 10000000, sender=deployer)
    return snekmate


@pytest.fixture
def tokens(solady, vypertoken, snekmate, oztoken):
    return solady, vypertoken, snekmate, oztoken

def test_tokens(tokens, sender, recipient):
    for token in tokens:
        assert token.balanceOf(sender) == 10000000
        assert token.balanceOf(recipient) == 0
        token.transfer(recipient, 1000, sender=sender)
        assert token.balanceOf(recipient) == 1000

        # repeat transfers
        for _ in range(10):
            token.transfer(recipient, 1000, sender=sender)

            token.approve(recipient, 1000, sender=sender)
            token.approve(recipient, 2000, sender=sender)
            token.transferFrom(sender, recipient, 500, sender=recipient)
            token.transferFrom(sender, recipient, 500, sender=recipient)
            token.transferFrom(sender, recipient, 500, sender=recipient)
            token.transferFrom(sender, recipient, 500, sender=recipient)

            token.approve(recipient, 1000, sender=sender)
            token.transferFrom(sender, recipient, 500, sender=recipient)
            token.transferFrom(sender, recipient, 500, sender=recipient)

            token.approve(recipient, 1000, sender=sender)
            token.transferFrom(sender, recipient, 1000, sender=recipient)
            token.approve(recipient, 0, sender=sender)
