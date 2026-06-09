pragma solidity 0.7.6;

interface ISavingsAccount {
    event Deposited(address indexed user, uint256 sharesReceived, address indexed token, address indexed strategy);

    event StrategySwitched(
        address indexed user,
        address indexed token,
        uint256 sharesDecreasedInCurrentStrategy,
        uint256 sharesIncreasedInNewStrategy,
        address currentStrategy,
        address indexed newStrategy
    );

    event Withdrawn(
        address indexed _from,
        address indexed to,
        uint256 sharesWithdrawn,
        address indexed token,
        address strategy,
        bool receiveShares
    );

    event WithdrawnAll(address indexed user, uint256 tokenReceived, address indexed token);

    event Approved(address indexed token, address indexed _from, address indexed to, uint256 amount);

    event Transfer(address indexed token, address strategy, address indexed _from, address indexed to, uint256 amount);

    event TransferShares(address indexed token, address strategy, address indexed _from, address indexed to, uint256 shares);

    event StrategyRegistryUpdated(address indexed updatedStrategyRegistry);

    function allowance(
        address user,
        address token,
        address to
    ) external returns (uint256 userAllowance);

    function deposit(
        address token,
        address strategy,
        address to,
        uint256 amount
    ) external returns (uint256 sharesReceived);

    function switchStrategy(
        address currentStrategy,
        address newStrategy,
        address token,
        uint256 amount
    ) external;

    function withdraw(
        address token,
        address strategy,
        address withdrawTo,
        uint256 amount,
        bool receiveShares
    ) external returns (uint256 amountWithdrawn);

    function withdrawAll(address token) external returns (uint256 tokenReceived);

    function withdrawAll(address token, address strategy) external returns (uint256 tokenReceived);

    function approve(
        address token,
        address to,
        uint256 amount
    ) external;

    function increaseAllowance(
        address token,
        address to,
        uint256 amount
    ) external;

    function decreaseAllowance(
        address token,
        address to,
        uint256 amount
    ) external;

    function transferShares(
        address _token,
        address _strategy,
        address _to,
        uint256 _shares
    ) external returns (uint256);

    function transfer(
        address token,
        address strategy,
        address to,
        uint256 amount
    ) external returns (uint256 tokensReceived);

    function transferSharesFrom(
        address token,
        address strategy,
        address _from,
        address to,
        uint256 _shares
    ) external returns (uint256);

    function transferFrom(
        address token,
        address strategy,
        address _from,
        address to,
        uint256 amount
    ) external returns (uint256 tokensReceived);

    function balanceInShares(
        address user,
        address token,
        address strategy
    ) external view returns (uint256 shareBalance);

    function withdrawFrom(
        address token,
        address strategy,
        address _from,
        address to,
        uint256 amount,
        bool receiveShares
    ) external returns (uint256 amountReceived);

    function withdrawShares(
        address token,
        address strategy,
        address to,
        uint256 shares,
        bool receiveShares
    ) external returns (uint256 amountReceived);

    function withdrawSharesFrom(
        address token,
        address strategy,
        address _from,
        address to,
        uint256 shares,
        bool receiveShares
    ) external returns (uint256 amountReceived);

    function getTotalTokens(address _user, address _token) external returns (uint256 _totalTokens);
}
