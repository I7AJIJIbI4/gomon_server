<?php

if (!function_exists('file_put_contents')) {
	if (!defined('FILE_USE_INCLUDE_PATH'))
		define('FILE_USE_INCLUDE_PATH', 1);
	if (!defined('FILE_APPEND'))
		define('FILE_APPEND', 8);
	if (!defined('LOCK_EX'))
		define('LOCK_EX', 2);
	function file_put_contents($filename, $data, $flags = 0, $context = false) {
		if (is_array($data)) $data = implode('', $data);
		$res = false;
		if (($fh = fopen($filename, (($flags & FILE_APPEND) ? 'a' : 'w'), (($flags & FILE_USE_INCLUDE_PATH) ? true : false)))) {
			$res = fwrite($fh, $data);
			fclose($fh);
		}
		return $res;
	}
}

if (!function_exists('json_decode')) {
	require_once dirname(__FILE__).'/class.json.php';
	global $_json_service;
	$_json_service = new Services_JSON();
	function json_decode($json, $assoc = false) {
		global $_json_service;
		$_json_service->use = $assoc ? SERVICES_JSON_LOOSE_TYPE : 0;
		return $_json_service->decode($json);
	}
	function json_encode($data, $assoc = false) {
		global $_json_service;
		$_json_service->use = $assoc ? SERVICES_JSON_LOOSE_TYPE : 0;
		return $_json_service->encodeUnsafe($data);
	}
}

if (false && !function_exists('escapeshellarg')) {
	/**
	 * @see https://stackoverflow.com/questions/58519037/how-do-i-use-escapeshellarg-on-windows-but-aimed-for-linux-and-vice-versa
	 */
	function escapeshellarg($input, $os_mode = 0) {
		$target_os_windows = 1;
		$target_os_unix = 2;
		if (false !== strpos($input, "\x00")) {
			throw new \UnexpectedValueException(__FUNCTION__ . '(): Argument #1 ($input) must not contain any null bytes');
		}
		if ($os_mode == 0) {
			$os_mode = $target_os_unix;
			if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN')
				$os_mode = $target_os_windows;
		}
		$maxlen = 4096;
		if ($os_mode === $target_os_windows) $maxlen = 8192;
		if (strlen($input) > $maxlen - 2) return "";

		if ($os_mode === $target_os_windows) {
			$output =
				str_replace(['"', '%', '!'],
							[' ', ' ', ' '],
							$input);
			# https://bugs.php.net/bug.php?id=69646
			if (substr($output, -1) === "\\") {
				$k = 0; $n = strlen($output) - 1;
				for (; $n >= 0 && substr($output, $n, 1) === "\\"; $n--, $k++);
				if ($k % 2) $output .= "\\";
			}
			$output = "\"$output\"";
		} else {
			$output = str_replace("'", "'\''", $input);
			$output = "'$output'";
		}
		if (strlen($output) > $maxlen) return "";
		return $output;
	}
}
if (false && !function_exists('escapeshellcmd')) {
	function escapeshellcmd($command) {
		return $command;
	}
}
