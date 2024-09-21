// SPDX-License-Identifier: MIT

pragma solidity ^0.8.27;

import "@solady/tokens/ERC20.sol";

contract SoladyToken is ERC20 {

    function name() public view override returns (string memory) {
        return "Solady Token";
    }

    function symbol() public view override returns (string memory) {
        return "SLDY";
    }

    constructor() {
        _mint(msg.sender, 1000000000000000000000000000);
    }

}
