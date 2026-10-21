pragma solidity =0.8.9;

contract VaderRouter is IVaderRouter, ProtocolConstants, Ownable {

    using SafeERC20 for IERC20;

    IVaderPoolFactory public immutable factory;

    IVaderReserve public reserve;

    function _swap(uint256 amountIn, address[] calldata path, address to) private returns (uint256 amountOut) {
        if (path.length == 3) {
            require(path[0] != path[1] && path[1] == factory.nativeAsset() && path[2] != path[1], "VaderRouter::_swap: Incorrect Path");

            IVaderPool pool0 = factory.getPool(path[0], path[1]);
            IVaderPool pool1 = factory.getPool(path[1], path[2]);

            IERC20(path[0]).safeTransferFrom(msg.sender, address(pool0), amountIn);

            return pool1.swap(0, pool0.swap(amountIn, 0, address(pool1)), to);
        } else {
            require(path.length == 2, "VaderRouter::_swap: Incorrect Path Length");
            address nativeAsset = factory.nativeAsset();
            require(path[0] != path[1], "VaderRouter::_swap: Incorrect Path");

            IVaderPool pool = factory.getPool(path[0], path[1]);
            IERC20(path[0]).safeTransferFrom(msg.sender, address(pool), amountIn);
            if (path[0] == nativeAsset) {
                return pool.swap(amountIn, 0, to);
            } else {
                require(path[1] == nativeAsset, "VaderRouter::_swap: Incorrect Path");
                return pool.swap(0, amountIn, to);
            }
        }
    }

}
