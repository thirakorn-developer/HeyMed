class ApiEndpoints {
  static const baseUrl = 'http://localhost:8000/api/v1';

  // Auth
  static const login = '/auth/login';
  static const register = '/auth/register';
  static const refresh = '/auth/refresh';
  static const me = '/auth/me';

  // Drugs
  static const drugSearch = '/drugs/search';
  static const drugAutocomplete = '/drugs/autocomplete';
  static String drugDetail(int rxcui) => '/drugs/$rxcui';
  static String drugIngredients(int rxcui) => '/drugs/$rxcui/ingredients';
  static String drugBrands(int rxcui) => '/drugs/$rxcui/brands';
  static String drugForms(int rxcui) => '/drugs/$rxcui/forms';
  static String drugNdc(int rxcui) => '/drugs/$rxcui/ndc';

  // Interactions
  static const interactionCheck = '/interactions/check';
  static String interactionsByDrug(int rxcui) => '/interactions/$rxcui';

  // Inventory
  static const inventory = '/inventory';
  static String inventoryItem(String id) => '/inventory/$id';
  static String inventoryAdjust(String id) => '/inventory/$id/adjust';
  static const inventoryAlerts = '/inventory/alerts';

  // Prescriptions
  static const prescriptions = '/prescriptions';
  static String prescription(String id) => '/prescriptions/$id';
  static String prescriptionDispense(String id) => '/prescriptions/$id/dispense';
  static String prescriptionAnalyze(String id) => '/prescriptions/$id/analyze';

  // Customers
  static const customers = '/customers';
  static String customer(String id) => '/customers/$id';

  // Chat
  static const chatSessions = '/chat/sessions';
  static String chatMessages(String sessionId) => '/chat/sessions/$sessionId/messages';
  static const chatQuick = '/chat/quick';
}
