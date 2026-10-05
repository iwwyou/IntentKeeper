pragma solidity =0.8.9;

interface ISynthFactory {
    function synths(IERC20 token) external view returns (ISynth);

    function createSynth(IERC20Extended token) external returns (ISynth);
}
