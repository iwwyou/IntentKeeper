pragma solidity =0.8.9;

contract VaderPoolV2 is IVaderPoolV2, BasePoolV2, Ownable {

    using SafeERC20 for IERC20;

    ILPWrapper public wrapper;

    ISynthFactory public synthFactory;

    bool public queueActive;

    function mintSynth(IERC20 foreignAsset, uint256 nativeDeposit, address _from, address to) external override nonReentrant supportedToken(foreignAsset) returns (uint256 amountSynth) {
        nativeAsset.safeTransferFrom(_from, address(this), nativeDeposit);

        ISynth synth = synthFactory.synths(foreignAsset);

        if (synth == ISynth(_ZERO_ADDRESS)) {
            synth = synthFactory.createSynth(IERC20Extended(address(foreignAsset)));
        }

        (uint112 reserveNative, uint112 reserveForeign, ) = getReserves(foreignAsset);

        amountSynth = VaderMath.calculateSwap(nativeDeposit, reserveNative, reserveForeign);

        _update(foreignAsset, reserveNative + nativeDeposit, reserveForeign, reserveNative, reserveForeign);

        synth.mint(to, amountSynth);
    }

}
