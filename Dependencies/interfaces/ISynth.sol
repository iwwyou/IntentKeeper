pragma solidity =0.8.9;

interface ISynth {
    function mint(address to, uint256 amount) external;

    function burn(uint256 amount) external;
}
