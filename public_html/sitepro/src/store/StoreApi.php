<?php

final class StoreApi {
	private function defineActions() {
		return array(
			'get' => array($this, 'getAction'),
			'set-order-state' => array($this, 'setOrderStateAction'),
		);
	}

	/** @return StoreApiResponse */
	protected function setOrderStateAction(StoreNavigation $request) {
		$error = StoreApiResponse::error('');
		if (!($data = self::requireData($request, $error))) {
			return $error;
		}
		if (!self::requireAuth($request, $data, $error)) {
			return $error;
		}

		$validFields = array(
			'id' => true,
			'transactionId' => true,
			'state' => true,
		);

		foreach ($data as $k => $v) {
			if (!isset($validFields[$k])) {
				return StoreApiResponse::error("Invalid field '{$k}'", 400);
			}
		}

		if (isset($data->id)) {
			if (!is_int($data->id)) {
				return StoreApiResponse::error("Field 'id' must be of type int", 400);
			}
			if ($data->id <= 0) {
				return StoreApiResponse::error("Field 'id' must be greater than 0", 400);
			}
		} else if (isset($data->transactionId)) {
			if (!is_string($data->transactionId)) {
				return StoreApiResponse::error("Field 'transactionId' must be of type string", 400);
			}
			if (strlen($data->transactionId) == 0) {
				return StoreApiResponse::error("Field 'transactionId' must be non-empty", 400);
			}
		} else {
			return StoreApiResponse::error("Field 'id' or 'transactionId' is required", 400);
		}

		if (isset($data->state)) {
			if (!is_string($data->state)) {
				return StoreApiResponse::error("Field 'state' must be of type string", 400);
			}
			if (!$data->state || !in_array($data->state, StoreModuleOrder::getStates())) {
				return StoreApiResponse::error("State '{$data->state}' is not valid", 400);
			}
		} else {
			return StoreApiResponse::error("Field 'state' is required", 400);
		}

		$order = null;
		if (isset($data->id)) {
			$order = StoreModuleOrder::findById($data->id);
			if (!$order) {
				return StoreApiResponse::error("Order ID {$data->id} not found", 400);
			}
		} else if (isset($data->transactionId)) {
			$order = StoreModuleOrder::findByTransactionId($data->transactionId);
			if (!$order) {
				return StoreApiResponse::error("Order TransactionID '{$data->transactionId}' not found", 400);
			}
		} else {
			return StoreApiResponse::error("Order not found", 400);
		}

		$order->setState($data->state)->save();
		$newState = $order->getState() ?: StoreModuleOrder::STATE_PENDING;

		return StoreApiResponse::json(['state' => $newState]);
	}

	/** @return StoreApiResponse */
	protected function getAction(StoreNavigation $request) {
		$error = StoreApiResponse::error('');
		if (!($data = self::requireData($request, $error))) {
			return $error;
		}
		if (!($apiKey = self::requireAuth($request, $data, $error))) {
			return $error;
		}

		$validFields = array(
			'key' => true,
			'settings' => true,
			'items' => true,
			'orders' => true,
			'categories' => true,
			'itemTypes' => true,
			'itemFieldTypes' => true,
		);

		foreach ($data as $k => $v) {
			if (!isset($validFields[$k])) {
				return StoreApiResponse::error("Invalid field '{$k}'", 400);
			}
		}

		$result = (object) array();

		foreach ($data as $k => $v) {
			if ($k == 'settings' && !self::buildSettings($result, $data, $error)) {
				return $error;
			}

			if ($k == 'items' && !self::buildItems($result, $data, $error)) {
				return $error;
			}
			
			if ($k == 'orders' && !self::buildOrders($result, $data, $error)) {
				return $error;
			}

			if ($k == 'categories' && !self::buildCategories($result, $data, $error)) {
				return $error;
			}

			if ($k == 'itemTypes' && !self::buildItemTypes($result, $data, $error)) {
				return $error;
			}

			if ($k == 'itemFieldTypes' && !self::buildItemFieldTypes($result, $data, $error)) {
				return $error;
			}
		}

		return StoreApiResponse::json($result);
	}

	/**
	 * @param object $result
	 * @param object $data
	 * @return bool
	 */
	private static function buildSettings(&$result, $data, StoreApiResponse &$error) {
		if (!isset($data->settings)) {
			return true;
		} else if (!is_object($data->settings)) {
			$error = StoreApiResponse::error("Field 'settings' must be object", 400);
			return false;
		}

		$result->settings = (object) array();
		$validFields = array(
			'currency',
			'stockSettings',
		);

		$includeFields = array();
		if (!self::prepareIncludeFields($data->settings, $includeFields, $validFields, 'settings', $error)) {
			return false;
		}
		if (empty($includeFields)) $includeFields = $validFields;

		foreach ($data->settings as $field => $v) {
			$error = StoreApiResponse::error("Invalid field settings.{$field}", 400);
			return false;
		}

		foreach ($includeFields as $field) {
			if ($field == 'currency') {
				$result->settings->currency = StoreData::getCurrency();
			} else if ($field == 'stockSettings') {
				$result->settings->stockSettings = StoreData::getStockSettings();
			}
		}

		return true;
	}

	/**
	 * @param object $result
	 * @param object $data
	 * @return bool
	 */
	private static function buildItems(&$result, $data, StoreApiResponse &$error) {
		if (!isset($data->items)) {
			return true;
		} else if (!is_object($data->items)) {
			$error = StoreApiResponse::error("Field 'items' must be object", 400);
			return false;
		}

		$result->items = array();
		$validFields = array(
			'id',
			'name',
			'description',
			'alias',
			'price',
			'fullPrice',
			'minPrice',
			'minFullPrice',
			'discount',
			'weight',
			'quantity',
			'maxQuantity',
			'sku',
			'image',
			'altImages',
			'itemType',
			'categories',
			'isHidden',
			'customFields',
			'variants',
			'dateTimeCreated',
			'dateTimeModified',
			'seoTitle',
			'seoDescription',
			'seoKeywords',
			'seoAlias',
			'stockManaged',
			'hasVariants',
		);

		if (!self::validateFields($data->items, $validFields, 'items', $error)) {
			return false;
		}
		$ok = self::matchItems($data->items, StoreData::getItems(),
				$result->items, $validFields,
				function($item, $fullItem) { self::expandItem($item, $fullItem); },
				'items', $error);
		if (!$ok) {
			return false;
		}

		return true;
	}

	/**
	 * @param \Profis\SitePro\controller\StoreDataItem $item
	 * @param \Profis\SitePro\controller\StoreDataItem $fullItem
	 * @return void
	 */
	private static function expandItem($item, $fullItem) {
		if (isset($item->itemType) && is_int($item->itemType)) {
			$itemType = StoreData::getItemType($item->itemType);
			$item->itemType = $itemType ? clone $itemType : null;
			unset($item->itemType->fields);
		}
		if (isset($item->categories) && is_array($item->categories)) {
			for ($i = 0, $c = count($item->categories); $i < $c; $i++) {
				$item->categories[$i] = is_int($item->categories[$i])
					? StoreData::getCategory($item->categories[$i])
					: null;
			}
		}
		if (isset($item->customFields) && is_array($item->customFields)) {
			$itemType = StoreData::getItemType($fullItem->itemType);
			if ($itemType) {
				for ($i = 0, $c = count($item->customFields); $i < $c; $i++) {
					$fld = $item->customFields[$i];
					$field = StoreData::getItemTypeField($itemType, $fld->fieldId);
					$fieldType = $field ? StoreData::getItemFieldType($field->type) : null;
					if ($field && $fieldType) {
						$item->customFields[$i] = clone $field;
						if (isset($fieldType->options) && is_array($fieldType->options)) {
							$values = array_flip(is_array($fld->value) ? $fld->value : array($fld->value));
							$item->customFields[$i]->value = array();
							foreach ($fieldType->options as $opt) {
								$newOpt = clone $opt;
								$newOpt->value = isset($values[$opt->id]);
								$item->customFields[$i]->value[] = $newOpt;
							}
						} else {
							$item->customFields[$i]->value = $fld->value;
						}
					} else {
						$item->customFields[$i] = null;
					}
				}
			} else {
				$item->customFields = array();
			}
		}
	}

	/**
	 * @param object $result
	 * @param object $data
	 * @return bool
	 */
	private static function buildOrders(&$result, $data, StoreApiResponse &$error) {
		if (!isset($data->orders)) {
			return true;
		} else if (!is_object($data->orders)) {
			$error = StoreApiResponse::error("Field 'orders' must be object", 400);
			return false;
		}

		$result->orders = array();
		$validFields = array(
			'id',
			'transactionId',
			'extTransactionId',
			'gatewayId',
			'lang',
			'buyer',
			'items',
			'price',
			'type',
			'state',
			'dateTime',
			'completeDateTime',
			'cancelDateTime',
			'stateDateTime',
			'billingInfo',
			'deliveryInfo',
			'orderComment',
			'taxAmount',
			'taxes',
			'shippingAmount',
			'shippingDescription',
			'currency',
			'priceOptions',
			'customFields',
			'invoiceDocumentNumber',
			'stockManaged',
			'stockAppliedVersion',
		);
		
		if (!self::validateFields($data->orders, $validFields, 'orders', $error)) {
			return false;
		}
		$ok = self::matchItems($data->orders, StoreModuleOrder::findAll(),
				$result->orders, $validFields,
				function() {},
				'orders', $error);
		
		if (!$ok) {
			return false;
		}
		
		return true;
	}

	/**
	 * @param object $result
	 * @param object $data
	 * @return bool
	 */
	private static function buildCategories(&$result, $data, StoreApiResponse &$error) {
		if (!isset($data->categories)) {
			return true;
		} else if (!is_object($data->categories)) {
			$error = StoreApiResponse::error("Field 'categories' must be object", 400);
			return false;
		}

		$result->categories = array();
		$validFields = array(
			'id',
			'parentId',
			'name',
			'description',
			'image',
			'viewType',
		);
		
		if (!self::validateFields($data->categories, $validFields, 'categories', $error)) {
			return false;
		}
		$ok = self::matchItems($data->categories, StoreData::getCategories(),
				$result->categories, $validFields,
				function() {},
				'categories', $error);
		if (!$ok) {
			return false;
		}
		
		return true;
	}

	/**
	 * @param object $result
	 * @param object $data
	 * @return bool
	 */
	private static function buildItemTypes(&$result, $data, StoreApiResponse &$error) {
		if (!isset($data->itemTypes)) {
			return true;
		} else if (!is_object($data->itemTypes)) {
			$error = StoreApiResponse::error("Field 'itemTypes' must be object", 400);
			return false;
		}

		$result->itemTypes = array();
		$validFields = array(
			'id',
			'name',
			'fields',
		);
		
		if (!self::validateFields($data->itemTypes, $validFields, 'itemTypes', $error)) {
			return false;
		}
		$ok = self::matchItems($data->itemTypes, StoreData::getItemTypes(),
				$result->itemTypes, $validFields,
				function() {},
				'itemTypes', $error);
		if (!$ok) {
			return false;
		}
		
		return true;
	}

	/**
	 * @param object $result
	 * @param object $data
	 * @return bool
	 */
	private static function buildItemFieldTypes(&$result, $data, StoreApiResponse &$error) {
		if (!isset($data->itemFieldTypes)) {
			return true;
		} else if (!is_object($data->itemFieldTypes)) {
			$error = StoreApiResponse::error("Field 'itemFieldTypes' must be object", 400);
			return false;
		}

		$result->itemFieldTypes = array();
		$validFields = array(
			'id',
			'name',
			'type',
			'typeId',
			'options',
			'isStatic',
		);
		
		if (!self::validateFields($data->itemFieldTypes, $validFields, 'itemFieldTypes', $error)) {
			return false;
		}
		$ok = self::matchItems($data->itemFieldTypes, StoreData::getItemFieldTypes(),
				$result->itemFieldTypes, $validFields,
				function() {},
				'itemFieldTypes', $error);
		if (!$ok) {
			return false;
		}
		
		return true;
	}

	/**
	 * @param object $def
	 * @param string[] $validFields
	 * @param string $property
	 * @param StoreApiResponse $error
	 * @return bool
	 */
	private static function validateFields($def, $validFields, $property, StoreApiResponse &$error) {
		$validIdx = array_flip($validFields);

		foreach ($def as $k => $v) {
			if ($k == '__fields' || $k == '__paging' || $k == '__expand') continue;
			list($field, $op) = self::parseFieldOp($k);

			if (!isset($validIdx[$field])) {
				$error = StoreApiResponse::error(
						"Invalid field"
						." {$property}.{$field}", 400);
				return false;
			} else if (!in_array($op, array('==', '!=', '>', '>=', '<', '<=', 'in'))) {
				$error = StoreApiResponse::error(
						"Invalid operator in"
						." {$property}.{$field} {$op} ".self::val($v), 400);
				return false;
			} else if ($op == 'in' && !is_array($v)) {
				$error = StoreApiResponse::error(
						"Value must be array for 'in' operator in".
						" {$property}.{$field} {$op} ".self::val($v), 400);
				return false;
			} else if (is_array($v) || is_object($v)) {
				$error = StoreApiResponse::error(
					"Value can't be array or object for '{$op}' operator in".
					" {$property}.{$field} {$op} ".self::val($v), 400);
			}
		}
		return true;
	}

	/**
	 * @param object $def
	 * @param object[] $items
	 * @param object[] $result
	 * @param string[] $validFields
	 * @param callable $expandHandler
	 * @param string $property
	 * @param StoreApiResponse $error 
	 * @return false
	 */
	private static function matchItems($def, $items, &$result, $validFields, $expandHandler, $property, StoreApiResponse &$error) {
		$includeFields = array();
		if (!self::prepareIncludeFields($def, $includeFields, $validFields, $property, $error)) {
			return false;
		}
		if (empty($includeFields)) $includeFields = $validFields;

		$paging = (object) array('page' => 0, 'num' => 100);
		if (!self::preparePaging($def, $paging, $property, $error)) {
			return false;
		}

		$expand = false;
		if (!self::prepareExpand($def, $expand, $property, $error)) {
			return false;
		}

		$cc = 0;
		foreach ($items as $itemRaw) {
			if (method_exists($itemRaw, 'jsonSerializeApi')) {
				$item = (object) $itemRaw->jsonSerializeApi();
			} else if (method_exists($itemRaw, 'jsonSerialize')) {
				$item = (object) $itemRaw->jsonSerialize();
			} else {
				$item = $itemRaw;
			}
			$matches = true;
			foreach ($def as $k => $v) {
				list($field, $op) = self::parseFieldOp($k);

				if (!isset($item->{$field})) {
					$matches = false;
					break;
				}

				if (
						($op == '==' && $item->{$field} != $v)
						|| ($op == '!=' && $item->{$field} == $v)
						|| ($op == '>'  && $item->{$field} <= $v)
						|| ($op == '>=' && $item->{$field} <  $v)
						|| ($op == '<'  && $item->{$field} >= $v)
						|| ($op == '<=' && $item->{$field} >  $v)
						|| ($op == 'in' && !in_array($item->{$field}, $v))) {
					$matches = false;
					break;
				}
			}

			if ($matches) {
				$cc++;
				if ($paging->num == 0 || $paging->page == 0) {
					$resultItem = self::filterFields($item, $includeFields);
					if ($expand) call_user_func($expandHandler, $resultItem, $item);
					$result[] = $resultItem;
				}
				if ($paging->num > 0 && $paging->num == $cc) {
					if ($paging->page > 0) {
						$cc = 0;
						$paging->page--;
					} else {
						break;
					}
				}
			}
		}

		return true;
	}

	/**
	 * @param string $key
	 * @return string[]
	 */
	private static function parseFieldOp($key) {
		$parts = explode(' ', $key, 2);
		$field = $parts[0];
		$op = isset($parts[1]) ? $parts[1] : '==';
		if ($op == '=') $op = '==';
		else if ($op == '<>') $op = '!=';

		return array($field, $op);
	}

	/**
	 * @param object $def
	 * @param bool $expand
	 * @param string $property
	 * @param StoreApiResponse $error
	 * @return bool
	 */
	private static function prepareExpand($def, &$expand, $property, StoreApiResponse &$error) {
		$fieldsKey = '__expand';

		if (isset($def->{$fieldsKey})) {
			if (!is_bool($def->{$fieldsKey})) {
				$error = StoreApiResponse::error("Field '{$property}.{$fieldsKey}' must be boolean", 400);
				return false;
			}

			$expand = $def->{$fieldsKey} ? true : false;

			unset($def->{$fieldsKey});
		}

		return true;
	}

	/**
	 * @param object $def
	 * @param object $paging
	 * @param string $property
	 * @param StoreApiResponse $error
	 * @return bool
	 */
	private static function preparePaging($def, &$paging, $property, StoreApiResponse &$error) {
		$fieldsKey = '__paging';

		if (isset($def->{$fieldsKey})) {
			if (!is_object($def->{$fieldsKey})) {
				$error = StoreApiResponse::error("Field '{$property}.{$fieldsKey}' must be object", 400);
				return false;
			}
			if (isset($def->{$fieldsKey}->page)) {
				if (!is_int($def->{$fieldsKey}->page) || $def->{$fieldsKey}->page < 0) {
					$error = StoreApiResponse::error(
							"Field '{$property}.{$fieldsKey}.page'"
							." must be integer number, that is >= 0", 400);
					return false;
				}
				$paging->page = intval($def->{$fieldsKey}->page);
			}
			if (isset($def->{$fieldsKey}->num)) {
				if (!is_int($def->{$fieldsKey}->num)
						|| $def->{$fieldsKey}->num < 1
						|| $def->{$fieldsKey}->num > 500) {
					$error = StoreApiResponse::error(
							"Field '{$property}.{$fieldsKey}.num'"
							." must be integer number, that is in range [1, 500]", 400);
					return false;
				}
				$paging->num = intval($def->{$fieldsKey}->num);
			}

			foreach ($def->{$fieldsKey} as $k => $v) {
				if ($k != 'page' && $k != 'num') {
					$error = StoreApiResponse::error("Unknown field '{$property}.{$fieldsKey}.{$k}'", 400);
					return false;
				}
			}
			
			unset($def->{$fieldsKey});
		}

		return true;
	}

	/**
	 * @param object $def
	 * @param string[] $includeFields
	 * @param string[] $validFields
	 * @param string $property
	 * @param StoreApiResponse $error
	 * @return bool
	 */
	private static function prepareIncludeFields($def, &$includeFields, $validFields, $property, StoreApiResponse &$error) {
		$fieldsKey = '__fields';
		$validIdx = array_flip($validFields);

		if (isset($def->{$fieldsKey})) {
			if (!is_array($def->{$fieldsKey}) || empty($def->{$fieldsKey})) {
				$error = StoreApiResponse::error(
						"Field '{$property}.{$fieldsKey}'"
						." must be non-empty string array", 400);
				return false;
			}
			foreach ($def->{$fieldsKey} as $fld) {
				if (!is_string($fld)) {
					$error = StoreApiResponse::error("Field '{$property}.{$fieldsKey}' must be string array", 400);
					return false;
				} else if (!isset($validIdx[$fld])) {
					$error = StoreApiResponse::error("Invalid field '{$fld}' in '{$property}.{$fieldsKey}'", 400);
					return false;
				}
				$includeFields[] = $fld;
			}
			unset($def->{$fieldsKey});
		}

		return true;
	}

	/**
	 * @param object $item
	 * @param string[] $includeFields
	 * @return object
	 */
	private static function filterFields($item, $includeFields) {
		if (empty($includeFields)) {
			return $item;
		} else {
			$result = (object) array();
			foreach ($includeFields as $fld) {
				if (isset($item->{$fld})) $result->{$fld} = $item->{$fld};
			}
			return $result;
		}
	}

	/**
	 * @param mixed $value
	 * @return string
	 */
	private static function val($value) {
		return json_encode($value,
				JSON_UNESCAPED_SLASHES
				| JSON_UNESCAPED_UNICODE);
	}

	/** @return object|null */
	private static function requireData(StoreNavigation $request, StoreApiResponse &$error) {
		$dataStr = $request->getBody();
		$data = json_decode($dataStr);
		if (json_last_error() != JSON_ERROR_NONE) {
			$error = StoreApiResponse::error("invalid data format", 400);
			return null;
		}
		if ($data && is_object($data)) {
			return $data;
		} else {
			$error = StoreApiResponse::error("invalid data", 400);
			return null;
		}
	}

	/**
	 * @param object $data
	 * @return object|null
	 */
	private static function requireAuth(StoreNavigation $request, $data, StoreApiResponse &$error) {
		$auth = $request->getAuthData();
		if ($auth->scheme == 'Bearer' && $auth->params) {
			$apiKey = StoreData::findApiKeyByKey($auth->params);
		} else if (isset($data->key) && is_string($data->key) && $data->key) {
			$apiKey = StoreData::findApiKeyByKey($data->key);
		} else {
			$error = StoreApiResponse::error("auth required", 403);
			return null;
		}
		if ($apiKey) {
			return $apiKey;
		} else {
			$error = StoreApiResponse::error("auth failed", 403);
			return null;
		}
	}

	/**
	 * @param StoreNavigation $request
	 * @return no-return
	 */
	public function process(StoreNavigation $request) {
		$route = $request->getArg(1);
		if (!$route) $route = 'index';
		$routes = $this->defineActions();
		if (isset($routes[$route]) && is_callable($routes[$route])) {
			$response = call_user_func($routes[$route], $request);
			if (!($response instanceof StoreApiResponse)) {
				header('Content-Type: text/plain', true, 500);
				echo 'Invalid response';
			} else {
				header('Content-Type: '.$response->contentType, true, $response->code);
				if (strpos($response->contentType, 'application/json') === 0) {
					$data = json_encode($response->body);
				} else {
					$data = is_string($response->body)
						? $response->body
						: json_encode($response->body);
				}
				$len = function_exists('mb_strlen')
					? mb_strlen($data, '8bit')
					: strlen($data);
				header('Content-Length: '.$len, true);
				echo $data;
			}
		} else {
			header('Connection: close', true, 404);
		}
		exit();
	}
}

final class StoreApiResponse {
	public $body;
	public $code;
	public $contentType;

	/**
	 * @param object $body
	 * @param int $code
	 * @param string $contentType
	 */
	public function __construct($body, $code = 200, $contentType = 'text/html') {
		$this->body = $body;
		$this->code = $code;
		$this->contentType = $contentType;
	}

	/**
	 * @param mixed $data
	 * @param int $code
	 * @return self
	 */
	public static function json($data, $code = 200) {
		return new self($data, $code, 'application/json; charset=utf-8');
	}

	/**
	 * @param string|Exception $message
	 * @return self
	 */
	public static function error($message, $code = 500) {
		return self::json(
				(object) array(
					'error' => (($message instanceof Exception) ? $message->getMessage() : $message)
				),
				$code);
	}
}
